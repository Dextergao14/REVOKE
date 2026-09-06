#!/usr/bin/env python3
"""Render several graded runs as one comparison table."""
import argparse, json, sys

COLS = [("CSR", "episode_compliant_success"), ("VFR", "episode_violation_free"),
        ("Comp", "episode_all_completed"), ("Viol", "probe_violation_rate"),
        ("Trap", "stale_trap_rate"), ("Lag", "adaptation_lag_mean"),
        ("Intf", "update_interference"), ("Attr", "staleness_attribution"),
        ("Canary", "canary_false_violation_rate")]
EVENTS = ["ADD", "CONFLICT", "SUPERSEDE", "CONDITION", "SUPPORT", "RETRACT"]


def load(path):
    last = None
    for line in open(path):
        r = json.loads(line)
        if "__summary__" in r:
            last = r["__summary__"]
    if last is None:
        sys.exit(f"{path} has no summary line -- rerun eval/grade.py with --output")
    return last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    args = ap.parse_args()
    rows = [(r.get("label", p), r) for p, r in ((p, load(p)) for p in args.results)]
    w = max(len(n) for n, _ in rows) + 2
    print("system".ljust(w) + "".join(c.rjust(8) for c, _ in COLS))
    print("-" * (w + 8 * len(COLS)))
    for name, r in rows:
        print(name.ljust(w) + "".join(
            ("-" if r.get(k) is None else f"{r[k]:.3f}").rjust(8) for _, k in COLS))
    print("\nviolation rate by event type")
    print("system".ljust(w) + "".join(e[:8].rjust(11) for e in EVENTS))
    print("-" * (w + 11 * len(EVENTS)))
    for name, r in rows:
        d = r["violation_rate_by_event"]
        print(name.ljust(w) + "".join(
            ("-" if d.get(e) is None else f"{d[e]:.3f}").rjust(11) for e in EVENTS))


if __name__ == "__main__":
    main()
