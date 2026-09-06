#!/usr/bin/env python3
"""Turn one graded trial episode into the data behind the analysis figure.

  python scripts/trial_analysis.py --item <full item json> --workflow <workflow result json> --out <dir>

Writes <out>/trace_<condition>.jsonl (grader format), <out>/graded_<condition>.json
and <out>/trial_data.json (ground-truth timeline + per-condition agent steps)."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from revoke.logic import Lit, check_assertion, lit, solve
from revoke.serialize import rulebase_at
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval"))
from grade import grade_item, resolve_entity


def gt_timeline(item):
    """Per session, per entity: licensed / forbidden / silent, plus the events."""
    allow = item["allow"]
    ents = sorted(item["entity_names"], key=lambda e: item["entity_names"][e])
    rows = []
    for s in range(0, item["n_sessions"] + 1):
        sol = solve(rulebase_at(item, s, allow))
        st = {}
        for e in ents:
            if check_assertion(sol, [lit(f"{allow}({e})")]).violation:
                st[e] = "forbidden"
            elif Lit(allow, (e,)) in sol.closure:
                st[e] = "licensed"
            else:
                st[e] = "silent"
        rows.append({"session": s, "status": st,
                     "deleted": sorted({n.rid for n in sol.deleted}),
                     "closure": sorted(str(l) for l in sol.closure)})
    events = [{"session": e["session"], "kind": e["kind"], "text": e["text"], "rid": e["rid"],
               "motif": e["motif"], "tags": e["tags"]} for e in item["events"]]
    return {"entities": [{"id": e, "name": item["entity_names"][e]} for e in ents],
            "timeline": rows, "events": events}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", required=True)
    ap.add_argument("--workflow", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    item = json.load(open(a.item))
    data = {"item": {k: item[k] for k in ("id", "domain", "domain_title", "regime", "density",
                                          "motifs", "n_sessions", "act_tool", "entity_names")},
            "sessions": item["sessions"],
            "probes": [{k: p[k] for k in ("probe_id", "session", "tests", "motif_name", "options",
                                          "compliant", "licensed", "violating", "stale_trap",
                                          "flip", "deleted_rules", "blamed")} for p in item["probes"]],
            "ground_truth": gt_timeline(item), "conditions": []}
    if a.workflow:
        wf = json.load(open(a.workflow))
        for cond in wf["conditions"]:
            steps = [{"probe_id": s["probe_id"],
                      "tool_calls": [{"name": c["name"], "arguments": {"x": c["argument"]}} for c in s.get("read_calls", [])]
                                    + [{"name": s["action"]["tool"], "arguments": {item["act_param"]: s["action"]["argument"]}}],
                      "text": s.get("reply", "")}
                     for s in cond["steps"] if s.get("probe_id") and s.get("action")]
            trace = {"id": item["id"], "steps": steps}
            path = os.path.join(a.out, f"trace_{cond['condition']}.jsonl")
            with open(path, "w") as f:
                f.write(json.dumps(trace) + "\n")
            g = grade_item(item, trace)
            json.dump(g, open(os.path.join(a.out, f"graded_{cond['condition']}.json"), "w"), indent=1)
            by_pid = {r["probe_id"]: r for r in g["probes"]}
            enriched = []
            for s in cond["steps"]:
                if not s.get("probe_id"):
                    enriched.append({"session": s["session"], "probe_id": None,
                                     "notes_after": s.get("notes_after")})
                    continue
                r = by_pid.get(s["probe_id"], {})
                chosen = resolve_entity(item, {"arguments": {"x": s["action"]["argument"]}}) if s.get("action") else ""
                enriched.append({**s, "chosen": chosen, "violation": r.get("violation"),
                                 "completed": r.get("completed"), "took_stale_trap": r.get("took_stale_trap"),
                                 "stale_support": r.get("stale_support", []),
                                 "n_reads": r.get("n_reads")})
            data["conditions"].append({"condition": cond["condition"], "mode": cond["mode"],
                                       "model": cond["model"], "steps": enriched,
                                       "summary": {k: g[k] for k in ("violation_free", "all_completed", "compliant_success")}})
            print(f"{cond['condition']:>12}: CSR={g['compliant_success']}  violation_free={g['violation_free']}  "
                  f"completed={sum(r['completed'] for r in g['probes'])}/{len(g['probes'])}  "
                  f"violations={[r['probe_id'].split('#')[1] for r in g['probes'] if r['violation']]}")
    json.dump(data, open(os.path.join(a.out, "trial_data.json"), "w"), indent=1)
    print("wrote", os.path.join(a.out, "trial_data.json"))


if __name__ == "__main__":
    main()
