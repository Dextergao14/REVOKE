#!/usr/bin/env python3
"""Draw a stratified sample of probes (domain x event type) and render each
with only the update turns that bear on its options -- a compact view for
reviewing what a single graded decision point looks like."""
import argparse, collections, json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/revoke_full.jsonl")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--traps-only", action="store_true")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    items = [json.loads(l) for l in open(a.dataset)]

    pool = collections.defaultdict(list)
    for it in items:
        for p in it["probes"]:
            if a.traps_only and not p["stale_trap"]:
                continue
            if "[echo]" in p["note"]:
                continue
            pool[(it["domain"], p["tests"])].append((it, p))
    keys = sorted(pool)
    rng.shuffle(keys)
    picked, ki = [], 0
    while len(picked) < a.n and any(pool.values()):
        k = keys[ki % len(keys)]
        ki += 1
        if pool[k]:
            picked.append(pool[k].pop(rng.randrange(len(pool[k]))))

    for n, (it, p) in enumerate(picked, 1):
        names = it["entity_names"]
        opts = set(p["option_names"])
        print(f"\n{'=' * 78}\n#{n:02d}  {it['id']}  ·  {it['domain_title']}  ·  "
              f"tests {p['tests']}  ·  motif {p['motif_name']}  ·  session {p['session']}"
              f"{'  ·  STALE TRAP' if p['stale_trap'] else ''}")
        print("-" * 78)
        shown = 0
        for s in it["sessions"]:
            if s["index"] > p["session"]:
                break
            for t in s["turns"]:
                if t["kind"] == "update" and any(o in t["text"] for o in opts):
                    print(f"  s{s['index']:>2}  {t['text']}")
                    shown += 1
                elif t["kind"] == "update" and any(
                        c in t["text"] for c in (
                            "as of today", "starting now", "Situation update",
                            "Chart update", "Noting", "By the way", "Just so you know",
                            "For the record", "As of now", "no longer")):
                    print(f"  s{s['index']:>2}  {t['text']}")
                    shown += 1
                if t.get("probe_id") == p["probe_id"]:
                    print(f"\n  s{s['index']:>2}  ▶ {t['text']}")
        print()
        print(f"  ✔ licensed        : {[names[e] for e in p['licensed']]}")
        print(f"  ✘ violation       : {[names[e] for e in p['violating']]}")
        unl = [names[e] for e in p["compliant"] if e not in p["licensed"]]
        print(f"  ○ safe, incomplete: {unl}")
        if p["stale_trap"]:
            print(f"  ⚠ stale trap      : {[names[e] for e in p['stale_trap']]}  "
                  f"(compliant at the previous probe on this option set)")
        if p["blamed"]:
            print(f"  blamed rules      : {p['blamed']}")
        print(f"  D_t               : {p['deleted_rules']}")


if __name__ == "__main__":
    main()
