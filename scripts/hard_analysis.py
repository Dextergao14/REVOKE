#!/usr/bin/env python3
"""Grade a multi-item, multi-condition workflow result against the full items
and break the failures down by motif and event type.

  python scripts/hard_analysis.py --full data/hard/pilot_full.jsonl --workflow <result.json> --out <dir>
"""
import argparse, collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval"))
from grade import grade_item, summarise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", required=True)
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    items = {json.loads(l)["id"]: json.loads(l) for l in open(a.full)}
    wf = json.load(open(a.workflow))
    by_cond = collections.defaultdict(list)
    for c in wf["conditions"]:
        by_cond[c["condition"]].append(c)
    report = {}
    for cond, runs in sorted(by_cond.items()):
        traces, graded, used = [], [], []
        for run in runs:
            it = items[run["id"]]
            steps = [{"probe_id": s["probe_id"],
                      "tool_calls": [{"name": r["name"], "arguments": {"x": r["argument"]}} for r in s.get("read_calls", [])]
                                    + [{"name": s["action"]["tool"], "arguments": {it["act_param"]: s["action"]["argument"]}}],
                      "text": s.get("reply", "")} for s in run["steps"] if s.get("action")]
            tr = {"id": it["id"], "steps": steps}
            traces.append(tr)
            g = grade_item(it, tr)
            attempted = {s["probe_id"] for s in steps}
            g["probes"] = [r for r in g["probes"] if r["probe_id"] in attempted]
            g["violation_free"] = not any(r["violation"] for r in g["probes"])
            g["all_completed"] = all(r["completed"] for r in g["probes"])
            g["compliant_success"] = g["violation_free"] and g["all_completed"]
            it2 = dict(it); it2["probes"] = [p for p in it["probes"] if p["probe_id"] in attempted]
            graded.append(g)
            used.append(it2)
        with open(os.path.join(a.out, f"trace_{cond}.jsonl"), "w") as f:
            for tr in traces:
                f.write(json.dumps(tr) + "\n")
        summ = summarise(used, graded)
        # failure breakdown
        fails = collections.Counter(); fails_m = collections.Counter(); n_m = collections.Counter(); n_e = collections.Counter()
        inc = collections.Counter(); detail = []
        for g, it in zip(graded, used):
            pm = {p["probe_id"]: p for p in it["probes"]}
            for r in g["probes"]:
                p = pm[r["probe_id"]]
                n_m[p["motif_name"]] += 1; n_e[p["tests"]] += 1
                if r["violation"]:
                    fails[p["tests"]] += 1; fails_m[p["motif_name"]] += 1
                    detail.append({"item": it["id"], "probe": r["probe_id"].split("#")[1], "session": p["session"],
                                   "motif": p["motif_name"], "tests": p["tests"], "chose": [it["entity_names"].get(e, e) for e in r["chosen"]],
                                   "licensed": [it["entity_names"][e] for e in p["licensed"]], "trap": r["took_stale_trap"], "note": p["note"]})
                elif not r["completed"]:
                    inc[p["motif_name"]] += 1
        report[cond] = {"summary": summ,
                        "violations_by_event": {k: f"{fails[k]}/{n_e[k]}" for k in sorted(n_e)},
                        "violations_by_motif": {k: f"{fails_m[k]}/{n_m[k]}" for k in sorted(n_m)},
                        "incomplete_by_motif": {k: f"{inc[k]}/{n_m[k]}" for k in sorted(n_m) if inc[k]},
                        "per_item": [{"id": g["id"], "violations": sum(r["violation"] for r in g["probes"]),
                                      "incomplete": sum((not r["completed"]) and not r["violation"] for r in g["probes"]),
                                      "n": len(g["probes"])} for g in graded],
                        "violations": detail}
        json.dump({"graded": graded}, open(os.path.join(a.out, f"graded_{cond}.json"), "w"), indent=1)
    json.dump(report, open(os.path.join(a.out, "hard_report.json"), "w"), indent=1)
    for cond, r in report.items():
        s = r["summary"]
        print(f"\n=== {cond} ===  episodes CSR={s['episode_compliant_success']} VFR={s['episode_violation_free']} | "
              f"probe violation={s['probe_violation_rate']} completion={s['probe_completion_rate']} trap={s['stale_trap_rate']} lag={s['adaptation_lag_mean']}")
        print("  per item      :", ", ".join(f"{x['id'].split('_')[2]} {x['violations']}V/{x['incomplete']}I/{x['n']}" for x in r["per_item"]))
        print("  viol by event :", r["violations_by_event"])
        print("  viol by motif :", {k: v for k, v in r["violations_by_motif"].items() if not v.startswith("0/")})
        print("  incomplete    :", r["incomplete_by_motif"])


if __name__ == "__main__":
    main()
