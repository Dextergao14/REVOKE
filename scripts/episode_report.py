#!/usr/bin/env python3
"""Grade continuous-episode runs and compare memory conditions.

  python scripts/episode_report.py --full data/hard/pilot_full.jsonl --runs runs/episodes
"""
import argparse, collections, glob, json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval"))
from grade import adaptation_lag, grade_item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", required=True)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--json-out", default="")
    a = ap.parse_args()
    items = {json.loads(l)["id"]: json.loads(l) for l in open(a.full)}

    rows = collections.defaultdict(lambda: {
        "agg": collections.Counter(), "by_event": collections.defaultdict(lambda: [0, 0]),
        "lags": [], "censored": 0, "cost": 0.0, "compactions": [], "ctx": [], "summ": [],
        "episodes": 0, "clean_episodes": 0})
    for path in sorted(glob.glob(os.path.join(a.runs, "*.jsonl"))):
        for line in open(path):
            r = json.loads(line)
            if r["id"] not in items:
                continue
            it = items[r["id"]]
            key = (r["model"], r["mode"], r.get("budget", 0))
            R = rows[key]
            R.setdefault("wnum", 0.0)
            R.setdefault("wden", 0.0)
            R.setdefault("tier", collections.defaultdict(lambda: [0, 0]))
            R.setdefault("trapv", [0, 0])
            acted = [s for s in r["steps"] if s.get("tool_calls")]
            R["cost"] += (r.get("usage") or {}).get("cost", 0) or 0
            R["agg"]["errors"] += len(r["steps"]) - len(acted)
            R["compactions"].append(len(r.get("compactions", [])))
            R["ctx"] += [s["ctx_tokens"] for s in acted if "ctx_tokens" in s]
            R["summ"] += [s["summary_chars"] for s in acted if s.get("summary_chars")]
            if not acted:
                continue
            g = grade_item(it, {"id": r["id"], "steps": acted})
            done = {s["probe_id"] for s in acted}
            g["probes"] = [x for x in g["probes"] if x["probe_id"] in done]
            pm = {p["probe_id"]: p for p in it["probes"]}
            R["episodes"] += 1
            R["clean_episodes"] += (not any(x["violation"] for x in g["probes"])
                                    and all(x["completed"] for x in g["probes"]))
            for x in g["probes"]:
                p = pm[x["probe_id"]]
                R["agg"]["n"] += 1
                w = x.get("weight", 1.0)
                R["wden"] += w
                R["wnum"] += w * x["violation"]
                R["tier"][x.get("span_tier", "?")][0] += 1
                R["tier"][x.get("span_tier", "?")][1] += x["violation"]
                if x["is_trap"]:
                    R["trapv"][0] += 1
                    R["trapv"][1] += x["violation"]
                R["agg"]["viol"] += x["violation"]
                R["agg"]["done"] += x["completed"]
                R["agg"]["csr"] += x["completed"] and not x["violation"]
                R["agg"]["attr"] += x["stale_attributed"]
                if p["stale_trap"]:
                    R["agg"]["traps"] += 1
                    R["agg"]["trap_hit"] += x["took_stale_trap"]
                b = R["by_event"][p["tests"]]
                b[0] += 1
                b[1] += x["violation"]
            it2 = dict(it)
            it2["probes"] = [pm[q] for q in sorted(done, key=lambda z: int(z.split("#p")[1]))]
            l, c = adaptation_lag(it2, g)
            R["lags"] += l
            R["censored"] += c

    out = []
    for (model, mode, budget), R in rows.items():
        A = R["agg"]
        if not A["n"]:
            continue
        out.append({
            "model": model, "mode": mode, "budget": budget,
            "episodes": R["episodes"], "n": A["n"], "errors": A["errors"],
            "csr": A["csr"] / A["n"], "viol": A["viol"] / A["n"], "done": A["done"] / A["n"],
            "trap": A["trap_hit"] / A["traps"] if A["traps"] else None,
            "attr": A["attr"] / A["viol"] if A["viol"] else None,
            "ep_csr": R["clean_episodes"] / R["episodes"] if R["episodes"] else 0,
            "lag": round(statistics.mean(R["lags"]), 2) if R["lags"] else None,
            "censored": R["censored"],
            "compactions": round(statistics.mean(R["compactions"]), 1) if R["compactions"] else 0,
            "ctx_tok": int(statistics.mean(R["ctx"])) if R["ctx"] else 0,
            "summary_chars": int(statistics.mean(R["summ"])) if R["summ"] else 0,
            "wviol": R["wnum"] / R["wden"] if R["wden"] else None,
            "mean_w": R["wden"] / A["n"] if A["n"] else None,
            "tierv": {k: (v[1] / v[0] if v[0] else None) for k, v in R["tier"].items()},
            "trapv": R["trapv"][1] / R["trapv"][0] if R["trapv"][0] else None,
            "cost": R["cost"],
            "by_event": {k: (v[1] / v[0] if v[0] else None) for k, v in sorted(R["by_event"].items())},
        })
    order = {"full": 0, "compact": 1, "truncate": 2}
    out.sort(key=lambda r: (r["model"], order.get(r["mode"], 9)))
    out.sort(key=lambda r: (r["model"], order.get(r["mode"], 9), r["budget"]))
    w = max(len(r["model"]) for r in out) + 1
    def f3(x):
        return "  -  " if x is None else f"{x:.3f}"
    print(f"{'model'.ljust(w)}{'mode':>9}{'budget':>7}{'n':>5}"
          f"{'viol':>8}{'wviol':>8}{'CSR':>8}{'done':>8}"
          f"{'near':>7}{'mid':>7}{'far':>7}{'trap':>7}{'ctx':>7}{'cmpct':>7}{'$':>7}")
    print("-" * (w + 100))
    for r in out:
        b = f"{r['budget']}" if r["budget"] else "full"
        print(f"{r['model'].ljust(w)}{r['mode']:>9}{b:>7}{r['n']:>5}"
              f"{f3(r['viol']):>8}{f3(r['wviol']):>8}{f3(r['csr']):>8}{f3(r['done']):>8}"
              f"{f3(r['tierv'].get('near')):>7}{f3(r['tierv'].get('mid')):>7}"
              f"{f3(r['tierv'].get('far')):>7}{f3(r['trapv']):>7}"
              f"{r['ctx_tok']:>7}{r['compactions']:>7.1f}{r['cost']:>7.3f}")
    print("  viol/CSR/done absolute; wviol difficulty-weighted; near/mid/far by recall span.")
    ev = ["ADD", "CONFLICT", "SUPERSEDE", "CONDITION", "SUPPORT", "RETRACT", "NOISE", "CANARY"]
    present = [e for e in ev if any(r["by_event"].get(e) is not None for r in out)]
    print(f"\nviolation rate by event type\n{'model + mode + budget'.ljust(w + 18)}"
          + "".join(e[:9].rjust(11) for e in present))
    print("-" * (w + 18 + 11 * len(present)))
    for r in out:
        tag = f"{r['model']} {r['mode']} {r['budget'] or 'full'}"
        print(f"{tag.ljust(w + 18)}" + "".join(
            ("  -  " if r["by_event"].get(e) is None else f"{r['by_event'][e]:.3f}").rjust(11)
            for e in present))
    print(f"\ntotal spend: ${sum(r['cost'] for r in out):.3f}")
    if a.json_out:
        json.dump(out, open(a.json_out, "w"), indent=1)


if __name__ == "__main__":
    main()
