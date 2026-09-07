#!/usr/bin/env python3
"""Grade every OpenRouter run in a directory and print one comparison table.

  python scripts/or_report.py --full <full.jsonl> --runs <dir> [--tier easy|hard]
"""
import argparse, collections, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval"))
from grade import grade_item

VENDOR = {"anthropic": "Anthropic", "openai": "OpenAI", "google": "Google", "x-ai": "xAI",
          "deepseek": "DeepSeek", "qwen": "Qwen", "z-ai": "Z.ai", "moonshotai": "Moonshot",
          "minimax": "MiniMax", "nvidia": "NVIDIA", "meta-llama": "Meta", "mistralai": "Mistral",
          "amazon": "Amazon", "inclusionai": "InclusionAI", "microsoft": "Microsoft", "cohere": "Cohere"}
OPEN = {"deepseek", "qwen", "z-ai", "moonshotai", "minimax", "nvidia", "meta-llama",
        "mistralai", "inclusionai", "google-gemma", "microsoft"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", required=True)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--json-out", default="")
    a = ap.parse_args()
    items = {json.loads(l)["id"]: json.loads(l) for l in open(a.full)}
    rows = []
    for path in sorted(glob.glob(os.path.join(a.runs, "*.jsonl"))):
        by_item = collections.defaultdict(list)
        model = None
        for line in open(path):
            r = json.loads(line)
            model = r["model"]
            by_item[r["id"]] += r["steps"]
        if model is None:
            continue
        agg = collections.Counter()
        wnum = wden = 0.0
        pts = 0.0
        tier = collections.defaultdict(lambda: [0, 0])
        trap_v = [0, 0]
        by_event = collections.defaultdict(lambda: [0, 0])
        cost = 0.0
        for iid, steps in by_item.items():
            if iid not in items:
                continue
            it = items[iid]
            acted = [s for s in steps if s.get("tool_calls")]
            cost += sum((s.get("usage") or {}).get("cost", 0) or 0 for s in steps)
            agg["errors"] += len(steps) - len(acted)
            # answers salvaged from a reasoning trace that ran out of output
            # budget are lower-confidence; count them so they can be discounted
            agg["recovered"] += sum(1 for s in acted
                                    if "[recovered from reasoning]" in (s.get("text") or ""))
            if not acted:
                continue
            clean = [s for s in acted
                     if "[recovered from reasoning]" not in (s.get("text") or "")]
            g = grade_item(it, {"id": iid, "steps": clean})
            done = {s["probe_id"] for s in clean}
            pm = {p["probe_id"]: p for p in it["probes"]}
            for r in g["probes"]:
                if r["probe_id"] not in done:
                    continue
                agg["n"] += 1
                w = r.get("weight", 1.0)
                wden += w
                wnum += w * r["violation"]
                pts += w * (-1 if r["violation"] else (1 if r["completed"] else 0))
                tier[r.get("span_tier", "?")][0] += 1
                tier[r.get("span_tier", "?")][1] += r["violation"]
                if r["is_trap"]:
                    trap_v[0] += 1
                    trap_v[1] += r["violation"]
                agg["viol"] += r["violation"]
                agg["done"] += r["completed"]
                agg["csr"] += r["completed"] and not r["violation"]
                p = pm[r["probe_id"]]
                if p["stale_trap"]:
                    agg["traps"] += 1
                    agg["trap_hit"] += r["took_stale_trap"]
                e = p["tests"]
                by_event[e][0] += 1
                by_event[e][1] += r["violation"]
        if not agg["n"]:
            continue
        vendor = model.split("/")[0]
        rows.append({"model": model, "vendor": VENDOR.get(vendor, vendor),
                     "open": vendor in OPEN or "gemma" in model,
                     "n": agg["n"], "errors": agg["errors"], "recovered": agg["recovered"],
                     "viol": agg["viol"] / agg["n"], "done": agg["done"] / agg["n"],
                     "csr": agg["csr"] / agg["n"],
                     "trap": agg["trap_hit"] / agg["traps"] if agg["traps"] else None,
                     "score": pts / wden if wden else None,
                     "points": pts, "max_points": wden,
                     "wviol": wnum / wden if wden else None,
                     "mean_w": wden / agg["n"] if agg["n"] else None,
                     "tier": {k: (v[1] / v[0] if v[0] else None) for k, v in tier.items()},
                     "trap_viol": trap_v[1] / trap_v[0] if trap_v[0] else None,
                     "cost": cost,
                     "by_event": {k: (v[1] / v[0] if v[0] else None) for k, v in sorted(by_event.items())}})
    rows.sort(key=lambda r: (-r["csr"], r["viol"]))
    w = max(len(r["model"]) for r in rows) + 1
    def f3(x):
        return "  -  " if x is None else f"{x:.3f}"
    print(f"{'model'.ljust(w)}{'src':>7}{'n':>5}{'viol':>8}{'wviol':>8}{'done':>8}"
          f"{'SCORE':>8}{'points':>9}{'/max':>8}"
          f"{'near':>7}{'mid':>7}{'far':>7}{'trap':>7}{'$':>7}")
    print("-" * (w + 92))
    for r in rows:
        print(f"{r['model'].ljust(w)}{'open' if r['open'] else 'closed':>7}{r['n']:>5}"
              f"{f3(r['viol']):>8}{f3(r['wviol']):>8}{f3(r['done']):>8}"
              f"{f3(r['score']):>8}{r['points']:>9.1f}{r['max_points']:>8.1f}"
              f"{f3(r['tier'].get('near')):>7}{f3(r['tier'].get('mid')):>7}{f3(r['tier'].get('far')):>7}"
              f"{f3(r['trap_viol']):>7}{r['cost']:>7.3f}")
    print("  viol/done absolute.  SCORE = sum(w*s)/sum(w), s = +1 compliant and completed,")
    print("  0 compliant but not completed, -1 violation.  1.0 perfect, 0.0 same as never acting,")
    print("  negative worse than abstaining.  near/mid/far = violation rate by recall span.")
    ev = ["ADD", "CONFLICT", "SUPERSEDE", "CONDITION", "SUPPORT", "RETRACT", "NOISE", "CANARY"]
    present = [e for e in ev if any(r["by_event"].get(e) is not None for r in rows)]
    print(f"\nviolation rate by event type\n{'model'.ljust(w)}" + "".join(e[:9].rjust(11) for e in present))
    print("-" * (w + 11 * len(present)))
    for r in rows:
        print(r["model"].ljust(w) + "".join(
            ("  -  " if r["by_event"].get(e) is None else f"{r['by_event'][e]:.3f}").rjust(11) for e in present))
    print(f"\ntotal spend on these runs: ${sum(r['cost'] for r in rows):.3f}")
    if a.json_out:
        json.dump(rows, open(a.json_out, "w"), indent=1)


if __name__ == "__main__":
    main()
