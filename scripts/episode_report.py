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
            "cost": R["cost"],
            "by_event": {k: (v[1] / v[0] if v[0] else None) for k, v in sorted(R["by_event"].items())},
        })
    order = {"full": 0, "compact": 1, "truncate": 2}
    out.sort(key=lambda r: (r["model"], order.get(r["mode"], 9)))
    w = max(len(r["model"]) for r in out) + 1
    print(f"{'model'.ljust(w)}{'mode':>10}{'n':>5}{'err':>5}{'CSR':>8}{'viol':>8}{'done':>8}"
          f"{'trap':>8}{'lag':>7}{'ctx':>7}{'cmpct':>7}{'notes':>7}{'$':>7}")
    print("-" * (w + 87))
    for r in out:
        t = f"{r['trap']:.3f}" if r["trap"] is not None else "  -  "
        lg = f"{r['lag']:.2f}" if r["lag"] is not None else "  -  "
        print(f"{r['model'].ljust(w)}{r['mode']:>10}{r['n']:>5}{r['errors']:>5}{r['csr']:>8.3f}"
              f"{r['viol']:>8.3f}{r['done']:>8.3f}{t:>8}{lg:>7}{r['ctx_tok']:>7}"
              f"{r['compactions']:>7.1f}{r['summary_chars']:>7}{r['cost']:>7.3f}")
    ev = ["ADD", "CONFLICT", "SUPERSEDE", "CONDITION", "SUPPORT", "RETRACT", "NOISE", "CANARY"]
    present = [e for e in ev if any(r["by_event"].get(e) is not None for r in out)]
    print(f"\nviolation rate by event type\n{'model + mode'.ljust(w + 10)}"
          + "".join(e[:9].rjust(11) for e in present))
    print("-" * (w + 10 + 11 * len(present)))
    for r in out:
        print(f"{(r['model'] + ' ' + r['mode']).ljust(w + 10)}" + "".join(
            ("  -  " if r["by_event"].get(e) is None else f"{r['by_event'][e]:.3f}").rjust(11)
            for e in present))
    print(f"\ntotal spend: ${sum(r['cost'] for r in out):.3f}")
    if a.json_out:
        json.dump(out, open(a.json_out, "w"), indent=1)


if __name__ == "__main__":
    main()
