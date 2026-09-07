#!/usr/bin/env python3
"""
Build the REVOKE dataset.

Generation is rejection sampling: a scenario is emitted only if the solver
accepts it (consistent closure at every timestep, no must-violate probe, the
over-deletion guard holds, and at least one probe where an option that used to
be compliant has become a violation).

    python eval/build_dataset.py --n 1000 --out data/
      -> data/revoke_full.jsonl     with ground truth; graders only
      -> data/revoke_blind.jsonl    hand THIS to agents
      -> data/revoke_core.jsonl     a 200-item stratified subset (blind)
      -> data/revoke_stats.json
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from revoke.domains.seeds import ALL
from revoke.generator import build_scenario
from revoke.hard import build_hard_scenario
from revoke.serialize import blind, scenario_to_item
from revoke.verify import verify

REGIMES = ["short", "long"]
DENSITY = ["sparse", "dense"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--out", default="data")
    ap.add_argument("--seed", type=int, default=20260905)
    ap.add_argument("--core", type=int, default=200)
    ap.add_argument("--tier", default="easy", choices=["easy", "hard"],
                    help="hard: speaker hierarchy, near-miss noise, long arcs")
    ap.add_argument("--cycles", type=int, default=6,
                    help="hard tier: extra repeats of each flip-style motif's state arc; "
                         "raises the compression ratio a memory system faces")
    ap.add_argument("--gap", default="", help="hard tier: 'lo,hi' sessions between beats")
    args = ap.parse_args()
    prefix = "revoke_full" if args.tier == "easy" else "revoke_hard"
    os.makedirs(args.out, exist_ok=True)

    rng = random.Random(args.seed)
    doms = list(ALL.values())
    items, rejected = [], collections.Counter()
    seed = args.seed
    cells = [(d, r, x) for d in doms for r in REGIMES for x in DENSITY]

    while len(items) < args.n:
        dom, regime, density = cells[len(items) % len(cells)]
        seed += 1
        sid = f"REVOKE_{dom.key}_{len(items):04d}"
        if args.tier == "hard":
            gap = tuple(int(x) for x in args.gap.split(",")) if args.gap else None
            sc = build_hard_scenario(dom, sid, seed, cycles=args.cycles, gap=gap)
        else:
            sc = build_scenario(dom, sid, seed, regime, density)
        rep = verify(sc, dom.allow)
        if not rep.ok:
            rejected[rep.failures[0].split(":")[-1].strip()[:48]] += 1
            continue
        items.append(scenario_to_item(sc, dom))

    rng.shuffle(items)
    for i, it in enumerate(items):
        it["id"] = f"REVOKE_{'hard_' if args.tier == 'hard' else ''}{it['domain']}_{i:04d}"
        for j, p in enumerate(it["probes"]):
            old = p["probe_id"]
            p["probe_id"] = f"{it['id']}#p{j}"
            for t in it["timeline"]:
                if t["probe_id"] == old:
                    t["probe_id"] = p["probe_id"]
            for s in it["sessions"]:
                for tn in s["turns"]:
                    if tn.get("probe_id") == old:
                        tn["probe_id"] = p["probe_id"]

    def dump(path, rows):
        with open(path, "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    stem = "revoke_full" if args.tier == "easy" else "revoke_hard_full"
    dump(os.path.join(args.out, stem + ".jsonl"), items)
    dump(os.path.join(args.out, stem.replace("full", "blind") + ".jsonl"), [blind(i) for i in items])

    # stratified core subset: even over domain x regime x density
    buckets = collections.defaultdict(list)
    for it in items:
        buckets[(it["domain"], it["regime"], it["density"])].append(it)
    core, k = [], 0
    while len(core) < min(args.core, len(items)):
        added = False
        for b in sorted(buckets):
            if k < len(buckets[b]):
                core.append(buckets[b][k])
                added = True
                if len(core) >= args.core:
                    break
        if not added:
            break
        k += 1
    dump(os.path.join(args.out, stem.replace("full", "core") + ".jsonl"), [blind(i) for i in core])

    stats = {
        "n_items": len(items),
        "n_core": len(core),
        "rejected": dict(rejected),
        "acceptance_rate": round(len(items) / (len(items) + sum(rejected.values())), 4),
        "by_domain": dict(collections.Counter(i["domain"] for i in items)),
        "by_regime": dict(collections.Counter(i["regime"] for i in items)),
        "by_density": dict(collections.Counter(i["density"] for i in items)),
        "n_probes": sum(len(i["probes"]) for i in items),
        "n_trap_probes": sum(1 for i in items for p in i["probes"] if p["stale_trap"]),
        "probes_by_event": dict(collections.Counter(
            p["tests"] for i in items for p in i["probes"])),
        "trap_by_event": dict(collections.Counter(
            p["tests"] for i in items for p in i["probes"] if p["stale_trap"])),
        "motif_usage": dict(collections.Counter(m for i in items for m in i["motifs"])),
        "events_by_kind": dict(collections.Counter(
            e["kind"] for i in items for e in i["events"])),
        "mean_sessions": round(sum(i["n_sessions"] for i in items) / len(items), 2),
        "mean_turns": round(sum(len(t["turns"]) for i in items
                                for t in i["sessions"]) / len(items), 2),
    }
    stats["tier"] = args.tier
    with open(os.path.join(args.out, stem.replace("full", "stats") + ".json"), "w") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
