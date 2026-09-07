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
                     "cost": cost,
                     "by_event": {k: (v[1] / v[0] if v[0] else None) for k, v in sorted(by_event.items())}})
    rows.sort(key=lambda r: (-r["csr"], r["viol"]))
    w = max(len(r["model"]) for r in rows) + 1
    print(f"{'model'.ljust(w)}{'src':>7}{'n':>5}{'err':>5}{'rec':>5}{'CSR':>8}{'viol':>8}{'done':>8}{'trap':>8}{'$':>8}")
    print("-" * (w + 62))
    for r in rows:
        t = f"{r['trap']:.3f}" if r["trap"] is not None else "  -  "
        print(f"{r['model'].ljust(w)}{'open' if r['open'] else 'closed':>7}{r['n']:>5}{r['errors']:>5}"
              f"{r['recovered']:>5}{r['csr']:>8.3f}{r['viol']:>8.3f}{r['done']:>8.3f}{t:>8}{r['cost']:>8.3f}")
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
