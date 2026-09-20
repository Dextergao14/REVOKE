#!/usr/bin/env python3
"""Estimate what an evaluation cell costs, by running it against a fake backbone.

    python3 scripts/cost_estimate.py --blind data/long100/long100_blind.jsonl.gz \
        --manifest data/long100/manifest.jsonl --memories compact,mem0,memos,memp,dynamic_cheatsheet \
        --price 0.09:0.30 --price 5:30

Replays ONE episode per named backend with a canned LLM (no network, no cost),
counts the memory-write and act calls and their prompt tokens, then scales by
the token ratio of the whole set to the probe episode and prints the bill at
each --price (input:output dollars per million).  The `full` condition is
computed analytically: every task resends the transcript prefix.

The point is to see, before spending anything, which cells are affordable: on
the long tier a method that scores every observation costs two orders of
magnitude more than one that writes once per task.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "eval", "adapters"))
os.environ.setdefault("OPENROUTER_API_KEY", "estimate")
os.environ["REVOKE_EMBED_HASH"] = "1"

from eval.memory import base                                        # noqa: E402
import memory_runner as MR                                          # noqa: E402

CANNED = ('{"memory": [{"text": "a fact"}]}\n<cheatsheet>\nsheet\n</cheatsheet>\nScore: 4')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blind", required=True)
    ap.add_argument("--manifest", default="")
    ap.add_argument("--memories", default="compact,mem0,memos,memp,dynamic_cheatsheet")
    ap.add_argument("--window", type=int, default=8000)
    ap.add_argument("--price", action="append", default=[], help="in:out dollars per million, repeatable")
    ap.add_argument("--episode", default="", help="which episode to probe (default: the shortest)")
    a = ap.parse_args()
    opener = gzip.open if a.blind.endswith(".gz") else open
    items = [json.loads(l) for l in opener(a.blind, "rt")]
    tok = {i["id"]: sum(len(t["text"]) for s in i["sessions"] for t in s["turns"]) // 4 for i in items}
    probe = next((i for i in items if i["id"] == a.episode), None) or min(items, key=lambda i: tok[i["id"]])
    total_tok = sum(tok.values())
    scale = total_tok / tok[probe["id"]]
    n_ep = len(items)
    print(f"probe episode {probe['id']}: {tok[probe['id']] // 1000}k tokens, {probe['n_sessions']} sessions, "
          f"{len(probe['probes'])} tasks\nset: {n_ep} episodes, {total_tok / 1e6:.1f}M tokens "
          f"(scale x{scale:.1f} from the probe)\n")

    def fake(self, messages, max_tokens=2000, tools=None, tool_choice="auto", memory_call=True, tries=3):
        self.usage["calls"] += 1
        n = sum(len(m["content"]) for m in messages) // 4
        if tools:
            txt = messages[-1]["content"]
            opt = (txt.split("options open to you right now are: ")[1].split(".")[0].split(", ")[0]
                   if "options open to you right now are: " in txt else "x")
            self.usage["act_in"] = self.usage.get("act_in", 0) + n
            return {"choices": [{"message": {"content": "ok", "tool_calls": [{"function": {
                "name": probe["act_tool"], "arguments": json.dumps({probe["act_param"]: opt})}}]}}],
                "usage": {"prompt_tokens": n, "completion_tokens": 20}}
        self.usage["memory_calls"] += 1
        self.usage["in"] += n
        self.usage["out"] += 60
        return {"choices": [{"message": {"content": CANNED}}], "usage": {"prompt_tokens": n, "completion_tokens": 60}}
    base.LLM.chat = fake

    prices = [tuple(float(x) for x in p.split(":")) for p in a.price] or [(0.09, 0.30), (5.0, 30.0)]
    head = f"{'condition':<22}{'mem calls':>10}{'in tok/ep':>12}{'out tok/ep':>11}"
    for pin, pout in prices:
        head += f"{f'${pin:g}/${pout:g}':>14}"
    print(head)
    print("-" * len(head))

    # analytic: full context resends the prefix at every task
    rows = []
    fin = sum(tok[i["id"]] * (len(i["probes"]) + 1) / 2 for i in items)
    rows.append(("full (no memory)", 0, fin / n_ep, 300 * sum(len(i["probes"]) for i in items) / n_ep))
    for name in a.memories.split(","):
        llm = base.LLM("fake/m", "k")
        try:
            backend = base.load_backend(name)(llm, {})
            MR.run_episode(probe, llm, backend, a.window, 4000, 500, "", False, 0, 0)
        except Exception as e:                                       # noqa: BLE001
            print(f"{name:<22}  FAILED {type(e).__name__}: {str(e)[:60]}")
            continue
        mem_calls = llm.usage["memory_calls"] * scale
        in_tok = (llm.usage["in"] + llm.usage.get("act_in", 0)) * scale
        out_tok = (llm.usage["out"] + 300 * len(probe["probes"])) * scale
        rows.append((name, mem_calls, in_tok / n_ep, out_tok / n_ep))
    for name, mem_calls, in_ep, out_ep in rows:
        line = f"{name:<22}{mem_calls / n_ep:>10.0f}{in_ep:>12,.0f}{out_ep:>11,.0f}"
        for pin, pout in prices:
            line += f"{(in_ep * n_ep * pin + out_ep * n_ep * pout) / 1e6:>13,.0f}$"
        print(line)
    print(f"\nper-cell totals are for all {n_ep} episodes; mem calls and tokens are per episode.")


if __name__ == "__main__":
    main()
