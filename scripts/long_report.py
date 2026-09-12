#!/usr/bin/env python3
"""Long-tier pilot report: one row per (condition, episode), plus per-probe detail.

    python3 scripts/long_report.py --full data/long/long_full.jsonl \
        --runs runs/long/episodes runs/long/full --detail
"""
import argparse, collections, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval"))
from grade import exam, grade_item


def cell_name(r):
    if r.get("mode", "full") == "full":
        return "full"
    return f"compact b{r['budget']} k{int(round(r.get('keep_frac', 0.55) * 100))}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--detail", action="store_true", help="list every violation")
    a = ap.parse_args()
    items = {json.loads(l)["id"]: json.loads(l) for l in open(a.full)}
    short = {k: k.split("_", 2)[2].rsplit("_", 1)[0] for k in items}
    rows = {}                                 # (model, cell, item) -> graded probes
    meta = {}
    for d in a.runs:
        for path in sorted(glob.glob(os.path.join(d, "*.jsonl")) + glob.glob(os.path.join(d, "*.jsonl.part"))):
            if path.endswith(".part") and os.path.exists(path[:-5]):
                continue
            for line in open(path):
                r = json.loads(line)
                if r["id"] not in items:
                    continue
                acted = [s for s in r["steps"] if s.get("tool_calls")]
                model = r.get("model") or f"scripted:{r.get('policy', '?')}"
                key = (model, "scripted" if "policy" in r else cell_name(r), r["id"])
                # .part files carry one step per line; merge
                bucket = rows.setdefault(key, {"steps": [], "partial": path.endswith(".part"),
                                               "compactions": 0, "cost": 0.0})
                bucket["steps"] += acted
                bucket["compactions"] += len(r.get("compactions", []))
                bucket["cost"] += ((r.get("usage") or {}).get("cost") or 0)
    out = []
    print(f"{'model':<20}{'condition':<20}{'episode':<16}{'tok':>6}{'n':>4}{'viol':>6}{'done':>6}{'abst':>6}{'EXAM':>7}{'far':>6}{'trap':>6}{'cmp':>6}{'$':>7}")
    print("-" * 116)
    agg = collections.defaultdict(list)
    for (model, cell, iid), b in sorted(rows.items(), key=lambda kv: (kv[0][0], kv[0][1], items[kv[0][2]]["meta"]["tokens"])):
        it = items[iid]
        g = grade_item(it, {"id": iid, "steps": b["steps"]})
        done_ids = {s["probe_id"] for s in b["steps"]}
        probes = [x for x in g["probes"] if x["probe_id"] in done_ids]
        if not probes:
            continue
        agg[(model, cell)] += probes
        n = len(probes)
        v = sum(x["violation"] for x in probes) / n
        d_ = sum(x["completed"] for x in probes) / n
        ab = sum((not x["violation"]) and (not x["completed"]) for x in probes) / n
        e = exam(probes)["score"]
        far = [x for x in probes if x["span_tier"] == "far"]
        tr = [x for x in probes if x["is_trap"]]
        fv = f"{sum(x['violation'] for x in far) / len(far):.2f}" if far else "  -  "
        tv = f"{sum(x['violation'] for x in tr) / len(tr):.2f}" if tr else "  -  "
        tag = short[iid] + ("*" if b["partial"] or n < len(it["probes"]) else "")
        print(f"{model[:19]:<20}{cell:<20}{tag:<16}{it['meta']['tokens'] // 1000:>5}k{n:>4}{v:>6.2f}{d_:>6.2f}{ab:>6.2f}{e:>+7.2f}{fv:>6}{tv:>6}{b['compactions']:>6}{b['cost']:>7.2f}")
        if a.detail:
            for x in probes:
                if x["violation"]:
                    p = next(p for p in it["probes"] if p["probe_id"] == x["probe_id"])
                    print(f"      VIOL {x['probe_id'].split('#')[1]:<4} s{x['session']:<4} span={x['recall_span']:<4} "
                          f"{'trap' if x['is_trap'] else '    '} {x['tests']:<10} chose {', '.join(it['entity_names'][c] for c in x['chosen'])}"
                          f"  | licensed: {', '.join(p['licensed_names'])}")
    print("-" * 116)
    for (model, cell), probes in sorted(agg.items()):
        n = len(probes)
        v = sum(x["violation"] for x in probes) / n
        d_ = sum(x["completed"] for x in probes) / n
        ab = sum((not x["violation"]) and (not x["completed"]) for x in probes) / n
        e = exam(probes)
        far = [x for x in probes if x["span_tier"] == "far"]; tr = [x for x in probes if x["is_trap"]]
        fv = f"{sum(x['violation'] for x in far) / len(far):.2f}" if far else "  -  "
        tv = f"{sum(x['violation'] for x in tr) / len(tr):.2f}" if tr else "  -  "
        print(f"{model[:19]:<20}{cell:<20}{'ALL':<16}{'':>6}{n:>4}{v:>6.2f}{d_:>6.2f}{ab:>6.2f}{e['score']:>+7.2f}{fv:>6}{tv:>6}"
              f"   wviol={sum(x['weight'] * x['violation'] for x in probes) / sum(x['weight'] for x in probes):.3f}")
    print("  * = partial (run still in progress); viol/done/abst unweighted; EXAM weighted in [-1, 1]")


if __name__ == "__main__":
    main()
