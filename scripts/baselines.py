#!/usr/bin/env python3
"""
Scripted reference policies.  No model calls -- these exist to show that the
benchmark separates behaviours the way it claims to, and to sanity-check the
grader before spending tokens on a real system.

  oracle    always picks a compliant option (upper bound)
  stale     reuses whatever worked last time it saw this option set --
            procedural memory invalidation in its purest form
  first     always picks the option that was mentioned first in the transcript
  recency   picks the option named in the most recent update turn
  refuse    never acts (shows why the completion gate is needed)
  random    uniform over the offered options

    python scripts/baselines.py --dataset data/revoke_full.jsonl \
        --policy stale --out runs/stale/trace.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run(item, policy, rng):
    steps, memory = [], {}
    turns = [t for s in item["sessions"] for t in s["turns"]]
    for p in item["probes"]:
        opts = p["options"]
        key = tuple(sorted(opts))
        if policy == "refuse":
            steps.append({"probe_id": p["probe_id"], "tool_calls": []})
            continue
        if policy == "oracle":
            pick = p["licensed"][0]
        elif policy == "random":
            pick = rng.choice(opts)
        elif policy == "stale":
            # first time it sees this choice set it solves it correctly; from
            # then on it replays the consolidated choice -- exactly what a
            # success-driven experiential memory does
            pick = memory.get(key) or p["licensed"][0]
        elif policy == "first":
            order = {}
            for i, t in enumerate(turns):
                for e in opts:
                    if item["entity_names"][e] in t["text"]:
                        order.setdefault(e, i)
            pick = min(opts, key=lambda e: order.get(e, 10 ** 6))
        elif policy == "recency":
            last = {}
            idx = next((i for i, t in enumerate(turns)
                        if t.get("probe_id") == p["probe_id"]), len(turns))
            for i, t in enumerate(turns[:idx]):
                if t["kind"] != "update":
                    continue
                for e in opts:
                    if item["entity_names"][e] in t["text"]:
                        last[e] = i
            pick = max(opts, key=lambda e: last.get(e, -1))
        else:
            raise SystemExit(f"unknown policy {policy}")
        memory[key] = pick
        steps.append({
            "probe_id": p["probe_id"],
            "tool_calls": [{"name": item["act_tool"],
                            "arguments": {item["act_param"]:
                                          item["entity_names"][pick]}}],
            "text": f"Used {item['entity_names'][pick]}.",
        })
    return {"id": item["id"], "policy": policy, "steps": steps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    items = [json.loads(l) for l in open(args.dataset)]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        for it in items:
            f.write(json.dumps(run(it, args.policy, rng)) + "\n")
    print(f"{len(items)} episodes -> {args.out}")


if __name__ == "__main__":
    main()
