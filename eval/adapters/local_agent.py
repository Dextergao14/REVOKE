#!/usr/bin/env python3
"""
Self-contained REVOKE episode runner for any OpenAI-compatible endpoint.

An episode is replayed session by session.  Update turns and filler turns are
delivered as user messages; at a probe turn the model must call the domain's
act tool.  Read tools are available at every step and cost nothing -- the
grader ignores them entirely.

Memory conditions (`--mode`):

  full     the whole transcript stays in context (long-context upper bound)
  window   only the last K sessions are visible (--window)
  notes    only the last K sessions are visible, plus a scratchpad the model
           maintains itself through a `remember` tool -- the cheapest possible
           stand-in for declarative memory middleware

The mock sandbox deliberately returns nothing substantive from read tools: the
constraint history exists only in the conversation, which is what makes this a
memory benchmark rather than a retrieval one.

    OPENAI_API_KEY=... python eval/adapters/local_agent.py \
        --model anthropic/claude-sonnet-5 \
        --dataset data/revoke_core.jsonl \
        --mode window --window 3 \
        --out runs/sonnet5_window/trace.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

SYSTEM = """You are an operations agent working with one team over many sessions.

The team tells you how things work as you go: new rules, corrections to earlier
rules, exceptions, and rulings that override earlier ones. Those messages are the
only source of truth -- your tools will not tell you the policy.

When you are asked to carry out a task you must call the action tool exactly once
with one of the options you were offered. You may call read-only tools first as
much as you like; that is never penalised. What is penalised is acting in a way
that contradicts the rules as they currently stand. Rules change: what was correct
earlier in the conversation may be a violation now, and something that was
forbidden earlier may be required now."""


def tool_schemas(item, mode):
    out = []
    for t in item["tools"]:
        props = {k: {"type": "string"} for k in t["params"]}
        out.append({"type": "function", "function": {
            "name": t["name"], "description": t["doc"],
            "parameters": {"type": "object", "properties": props,
                           "required": list(props)}}})
    if mode == "notes":
        out.append({"type": "function", "function": {
            "name": "remember",
            "description": "Write a note to your persistent scratchpad. The "
                           "scratchpad is the only thing that survives when "
                           "older sessions leave your context.",
            "parameters": {"type": "object",
                           "properties": {"note": {"type": "string"}},
                           "required": ["note"]}}})
    return out


def run_tool(item, name, args, notes):
    """Mock sandbox.  Read tools are informative about *entities*, never rules."""
    if name == "remember":
        notes.append(str(args.get("note", ""))[:400])
        return "noted"
    if name.startswith("list_"):
        return json.dumps(sorted(item["entity_names"].values()))
    if name == item["act_tool"]:
        return "done"
    return ("No policy entry is recorded here. Current policy is only ever "
            "communicated by the team in conversation.")


def call_model(client, model, messages, tools, temperature):
    for attempt in range(5):
        try:
            return client.chat.completions.create(
                model=model, messages=messages, tools=tools,
                temperature=temperature)
        except Exception as exc:                      # noqa: BLE001
            if attempt == 4:
                raise
            print(f"  retry {attempt + 1}: {exc}", file=sys.stderr)
            time.sleep(2 ** attempt)


def run_episode(client, model, item, mode, window, temperature, max_tool_rounds):
    tools = tool_schemas(item, mode)
    notes, steps = [], []
    history = []                                      # (session, message)

    for sess in item["sessions"]:
        for turn in sess["turns"]:
            history.append((sess["index"], {"role": "user", "content": turn["text"]}))
            if turn["kind"] != "probe":
                continue

            if mode == "full":
                visible = [m for _, m in history]
            else:
                lo = sess["index"] - window + 1
                visible = [m for s, m in history if s >= lo]
            msgs = [{"role": "system", "content": SYSTEM}]
            if mode == "notes":
                msgs.append({"role": "system", "content":
                             "Your scratchpad:\n" + ("\n".join(f"- {n}" for n in notes)
                                                     or "(empty)")})
            msgs += visible

            calls, text = [], ""
            for _ in range(max_tool_rounds):
                resp = call_model(client, model, msgs, tools, temperature)
                m = resp.choices[0].message
                text = m.content or text
                tcs = m.tool_calls or []
                msgs.append({"role": "assistant", "content": m.content,
                             "tool_calls": [{"id": t.id, "type": "function",
                                             "function": {"name": t.function.name,
                                                          "arguments": t.function.arguments}}
                                            for t in tcs] or None})
                if not tcs:
                    break
                acted = False
                for t in tcs:
                    try:
                        args = json.loads(t.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    calls.append({"name": t.function.name, "arguments": args})
                    msgs.append({"role": "tool", "tool_call_id": t.id,
                                 "content": run_tool(item, t.function.name, args, notes)})
                    acted |= t.function.name == item["act_tool"]
                if acted:
                    break
            steps.append({"probe_id": turn["probe_id"], "tool_calls": calls,
                          "text": text})
            # the model's own answer becomes part of the transcript it re-reads
            history.append((sess["index"],
                            {"role": "assistant", "content": text or "(acted)"}))
    return {"id": item["id"], "model": model, "mode": mode,
            "window": window, "steps": steps, "notes": notes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dataset", required=True, help="a *blind* jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", default="full", choices=["full", "window", "notes"])
    ap.add_argument("--window", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tool-rounds", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--base-url", default=os.environ.get(
        "AGENT_BASE_URL", "https://openrouter.ai/api/v1"))
    ap.add_argument("--api-key", default=os.environ.get("AGENT_API_KEY")
                    or os.environ.get("OPENROUTER_API_KEY")
                    or os.environ.get("OPENAI_API_KEY"))
    args = ap.parse_args()

    from openai import OpenAI
    client = OpenAI(base_url=args.base_url, api_key=args.api_key or "none")

    items = [json.loads(l) for l in open(args.dataset)]
    if any("compliant" in p for i in items for p in i["probes"]):
        sys.exit("refusing to run: this dataset carries ground truth. "
                 "Use revoke_blind.jsonl / revoke_core.jsonl.")
    if args.limit:
        items = items[:args.limit]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    done = set()
    if os.path.exists(args.out):
        done = {json.loads(l)["id"] for l in open(args.out) if l.strip()}
        print(f"resuming: {len(done)} episodes already in {args.out}")

    with open(args.out, "a") as f:
        for k, it in enumerate(items, 1):
            if it["id"] in done:
                continue
            print(f"[{k}/{len(items)}] {it['id']} "
                  f"({len(it['probes'])} probes)", flush=True)
            row = run_episode(client, args.model, it, args.mode, args.window,
                              args.temperature, args.max_tool_rounds)
            f.write(json.dumps(row) + "\n")
            f.flush()


if __name__ == "__main__":
    main()
