#!/usr/bin/env python3
"""Rank models on a set of graded runs and print the best by exam score.

    python3 scripts/pick_best.py --full data/long100/long100_full.jsonl.gz --runs runs/long100/full_open

Ties on exam are broken by lower violation rate.  Prints one line per model
(exam, violation, completion, abstention, n) and, on the last line, the model
id alone so a shell can capture it:  BEST=$(python3 scripts/pick_best.py ... | tail -1)
"""
from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "eval"))
from grade import exam, grade_item                                   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--min-tasks", type=int, default=1)
    ap.add_argument("--mode", default="full", help="only rank runs of this memory condition (default full); 'any' to pool")
    a = ap.parse_args()
    opener = gzip.open if a.full.endswith(".gz") else open
    items = {json.loads(l)["id"]: json.loads(l) for l in opener(a.full, "rt")}
    per_model = collections.defaultdict(list)
    for d in a.runs:
        for path in glob.glob(os.path.join(d, "*.jsonl")):
            for line in open(path):
                r = json.loads(line)
                if r.get("id") not in items or "steps" not in r:
                    continue
                if a.mode != "any" and r.get("mode", "full") != a.mode:
                    continue
                acted = [s for s in r["steps"] if s.get("tool_calls")]
                g = grade_item(items[r["id"]], {"id": r["id"], "steps": acted})
                done = {s["probe_id"] for s in r["steps"]}
                per_model[r["model"]] += [x for x in g["probes"] if x["probe_id"] in done]
    rows = []
    for m, probes in per_model.items():
        if len(probes) < a.min_tasks:
            continue
        n = len(probes)
        v = sum(x["violation"] for x in probes) / n
        d = sum(x["completed"] for x in probes) / n
        ab = sum((not x["violation"]) and (not x["completed"]) for x in probes) / n
        rows.append((exam(probes)["score"], -v, m, v, d, ab, n))
    rows.sort(reverse=True)
    print(f"{'model':<34}{'exam':>7}{'viol':>7}{'done':>7}{'abst':>7}{'n':>6}")
    for e, _, m, v, d, ab, n in rows:
        print(f"{m:<34}{e:>+7.3f}{v:>7.3f}{d:>7.3f}{ab:>7.3f}{n:>6}")
    if rows:
        print(rows[0][2])


if __name__ == "__main__":
    main()
