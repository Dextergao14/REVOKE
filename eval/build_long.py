#!/usr/bin/env python3
"""
Build long-context episodes (300k-1M tokens) from schema-v2 corpora.

    python3 eval/build_long.py --out data/long --probes 10 --seed 11 \
        --plan clinical_ward=300000,devops_release=450000,design_system=600000,companion=800000,game_narrative=1000000

Per episode: build_hard_scenario -> verify -> render_long -> select probes ->
verify the rendered subset -> item (full + blind).  Generation is rejection
sampling as elsewhere: a seed that fails any acceptance check is skipped.

Probe selection.  The generator emits one task per motif beat (~180 per
episode).  A released episode carries `--probes` of them, chosen from ground
truth alone: 20% from the first third of the episode, 30% from the middle, 50%
from the last third, preferring stale-memory traps, higher difficulty weight,
and a spread of event types, never two in one session and never an echo probe.
The unselected task turns are removed from the transcript, so the log reads as
months of conversation with a handful of moments where the agent is asked to
act.  The state history behind each kept probe is unchanged, so its trap and
recall-span labels stay valid.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import random
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from revoke.domains.corpus import CORPORA, load_corpus          # noqa: E402
from revoke.hard import build_hard_scenario                      # noqa: E402
from revoke.render_long import render_long                        # noqa: E402
from revoke.serialize import add_difficulty, blind, scenario_to_item  # noqa: E402
from revoke.verify import verify                                  # noqa: E402

BANDS = ((0.0, 1 / 3, 0.2), (1 / 3, 2 / 3, 0.3), (2 / 3, 1.01, 0.5))


def crutch_probes(item, old: int = 100) -> set:
    """Probes whose every licensed option was approved more than `old` sessions
    earlier and never restricted since -- answerable by spotting what was never
    touched, without tracking any state change.  Computed from ground truth."""
    from revoke.serialize import rulebase_at
    from revoke.logic import Lit, check_assertion, solve
    allow = item["allow"]
    ents = list(item["entity_names"])
    forbidden = {e: [] for e in ents}
    licensed_from = {}
    for s_ in sorted({e["session"] for e in item["events"]}):
        sol = solve(rulebase_at(item, s_, allow))
        for e in ents:
            if check_assertion(sol, [Lit(allow, (e,))]).violation:
                forbidden[e].append(s_)
            elif Lit(allow, (e,)) in sol.closure:
                licensed_from.setdefault(e, s_)
    out = set()
    for p in item["probes"]:
        lic = p["licensed"]
        if lic and all(not any(f < p["session"] for f in forbidden[e])
                       and p["session"] - licensed_from.get(e, p["session"]) > old for e in lic):
            out.add(p["probe_id"])
    return out


def select_probes(item, k: int, rng: random.Random, excluded: set, crutch: set = frozenset()) -> list:
    n = item["n_sessions"]
    used_sessions, types, chosen = set(), collections.Counter(), []
    quotas = [round(k * q) for _, _, q in BANDS]
    quotas[-1] += k - sum(quotas)
    for (lo, hi, _), quota in zip(BANDS, quotas):
        cand = [p for p in item["probes"]
                if lo * n <= p["session"] < hi * n and "[echo]" not in p["note"]
                and p["probe_id"] not in excluded]
        for _ in range(quota):
            cand = [p for p in cand if p["session"] not in used_sessions]
            if not cand:
                break

            def score(p):
                d = p["difficulty"]
                trap = bool(p["stale_trap"])
                s = 1.2 * trap + d["weight"] + 0.5 * (d["span_tier"] == "far")
                s -= 0.7 * types[p["tests"]]
                # keep some non-trap probes so trap / non-trap can be compared
                # within the tier; ~70% traps is the target
                if trap and types["_trap"] >= round(0.7 * k):
                    s -= 2.5
                if p["tests"] == "CANARY" and types["CANARY"]:
                    s -= 3
                # the licensed answer should depend on the history, not on
                # what was never mentioned
                if p["probe_id"] in crutch:
                    s -= 2.0
                return s + rng.random() * 0.05
            best = max(cand, key=score)
            chosen.append(best)
            used_sessions.add(best["session"])
            types[best["tests"]] += 1
            types["_trap"] += bool(best["stale_trap"])
    return chosen


def subset(sc, keep_ids: list):
    """Scenario with only the kept probes and their task turns, renumbered."""
    order = {pid: i for i, pid in enumerate(keep_ids)}
    new_id = {pid: f"{sc.sid}#p{i}" for pid, i in order.items()}
    probes = sorted((p for p in sc.probes if p.probe_id in order), key=lambda p: order[p.probe_id])
    turns = []
    for t in sc.turns:
        if t.kind == "probe":
            if t.probe_id not in order:
                continue
            t = replace(t, probe_id=new_id[t.probe_id])
        turns.append(t)
    pos = {t.probe_id: i for i, t in enumerate(turns) if t.probe_id}
    out = []
    for p in probes:
        q = replace(p, probe_id=new_id[p.probe_id])
        q.turn_index = pos[q.probe_id]
        out.append(q)
    return replace(sc, turns=turns, probes=out)


def build_one(corpus_path: str, target: int, k: int, seed: int, cycles: int, tries: int = 12):
    dom = load_corpus(corpus_path)
    corpus = CORPORA[dom.key]
    rng = random.Random(seed)
    for attempt in range(tries):
        s = seed + attempt
        sid = f"REVOKE_long_{dom.key}_{s}"
        sc = build_hard_scenario(dom, sid, s, cycles=cycles)
        rep = verify(sc, dom.allow)
        if not rep.ok:
            print(f"  seed {s}: rejected ({rep.failures[0][:70]})", flush=True)
            continue
        rendered = render_long(sc, corpus, seed=s, target_tokens=target)
        full = add_difficulty(scenario_to_item(rendered, dom))
        crutch = crutch_probes(full)
        excluded: set = set()
        for _ in range(6):
            picks = select_probes(full, k, rng, excluded, crutch)
            if len(picks) < k:
                break
            sub = subset(rendered, [p["probe_id"] for p in sorted(picks, key=lambda p: p["session"])])
            rep2 = verify(sub, dom.allow)
            if rep2.ok:
                item = add_difficulty(scenario_to_item(sub, dom))
                item["setting"] = corpus["setting"]
                item["you_prefix"] = corpus["surface"]["you_prefix"]
                item["corpus"] = os.path.basename(corpus_path)
                item["tier"] = "long"
                item["meta"]["crutch_probes"] = sum(1 for p in picks if p["probe_id"] in crutch)
                item["meta"]["crutch_pool"] = f"{len(crutch)}/{len(full['probes'])}"
                return item, rep2
            # a failing probe is named in the message; drop it and re-pick
            bad = {f.split(":")[0] for f in rep2.failures if "#p" in f.split(":")[0]}
            back = {}
            for old, new in zip(sorted(picks, key=lambda p: p["session"]), sub.probes):
                back[new.probe_id] = old["probe_id"]
            hit = {back[b] for b in bad if b in back}
            if not hit:
                print(f"  seed {s}: subset rejected ({rep2.failures[0][:70]})", flush=True)
                break
            excluded |= hit
        print(f"  seed {s}: could not assemble a clean {k}-probe subset", flush=True)
    raise RuntimeError(f"{corpus_path}: no acceptable episode in {tries} seeds")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="key=target_tokens,key=target_tokens,...")
    ap.add_argument("--corpora", default="revoke/domains/corpora")
    ap.add_argument("--out", default="data/long")
    ap.add_argument("--probes", type=int, default=10)
    ap.add_argument("--cycles", type=int, default=6)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    plan = [(kv.split("=")[0], int(kv.split("=")[1])) for kv in a.plan.split(",")]
    items = []
    for i, (key, target) in enumerate(plan):
        print(f"[{key}] target {target // 1000}k tokens", flush=True)
        item, rep = build_one(os.path.join(a.corpora, f"{key}.json"), target, a.probes,
                              a.seed + 100 * i, a.cycles)
        items.append(item)
        m = item["meta"]
        tiers = collections.Counter(p["difficulty"]["span_tier"] for p in item["probes"])
        tests = collections.Counter(p["tests"] for p in item["probes"])
        print(f"  ok  {item['id']}: {m['tokens'] // 1000}k tok ({m['format']}), "
              f"{item['n_sessions']} sessions, {len(item['probes'])} probes, "
              f"traps {sum(1 for p in item['probes'] if p['stale_trap'])}, "
              f"span {dict(tiers)}, tests {dict(tests)}, "
              f"mean w {sum(p['difficulty']['weight'] for p in item['probes']) / len(item['probes']):.2f}, "
              f"pad dup {m['pad_dup_rate']:.1%}, crutch {m['crutch_probes']}/{len(item['probes'])} "
              f"(pool {m['crutch_pool']})", flush=True)
        with open(os.path.join(a.out, f"{key}_full.jsonl"), "w") as fh:
            fh.write(json.dumps(item) + "\n")
        with open(os.path.join(a.out, f"{key}_blind.jsonl"), "w") as fh:
            fh.write(json.dumps(blind(item)) + "\n")
    with open(os.path.join(a.out, "long_full.jsonl"), "w") as fh:
        for it in items:
            fh.write(json.dumps(it) + "\n")
    with open(os.path.join(a.out, "long_blind.jsonl"), "w") as fh:
        for it in items:
            fh.write(json.dumps(blind(it)) + "\n")
    print(f"\nwrote {len(items)} episodes to {a.out}/")


if __name__ == "__main__":
    main()
