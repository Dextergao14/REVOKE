#!/usr/bin/env python3
"""
Run REVOKE probes against any OpenRouter model.

Probes are graded independently: each call gets the whole transcript up to that
probe and must act once.  The agent's own earlier replies are NOT replayed, so
every probe is a clean single-decision measurement and the whole run
parallelises.  The rule history is still in the transcript, so stale-memory
traps bite exactly as they do in the episode protocol; what is not measured this
way is a system reusing *its own* past action.

    export OPENROUTER_API_KEY=...
    python eval/adapters/openrouter_runner.py \
        --blind data/hard/pilot_blind.jsonl \
        --models qwen/qwen3.8-flash,deepseek/deepseek-v4-pro \
        --last 12 --out runs/or
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM = """You are an operations agent working with one team over many sessions (domain: {domain}; everything is synthetic).

The team tells you how things work as you go: new rules, corrections to earlier rules, exceptions, and rulings that override earlier ones. Those messages are the only source of truth -- your tools return no policy information. Different people speak in the conversation, and the first message explains whose statements count as policy.

You will be shown the conversation up to a task you must carry out now. Call {act} exactly once with one of the options you were offered. Acting in a way that contradicts the rules as they currently stand is a failure, and so is picking something nobody with authority ever approved."""

USER_TAIL = """

---
Act on the last message. Call the `{act}` tool exactly once with one of the offered options."""

JSON_TAIL = """

---
Act on the last message. Reply with ONLY a JSON object, no prose:
{{"{param}": "<the option name exactly as offered>"}}"""


def render(item, probe_id):
    """Transcript up to and including the probe turn (blind item only)."""
    target = next(s["index"] for s in item["sessions"] for t in s["turns"]
                  if t.get("probe_id") == probe_id)
    out = []
    for s in item["sessions"]:
        if s["index"] > target:
            break
        out.append(f"[Session {s['index']}]")
        for t in s["turns"]:
            out.append(t["text"])
            if t.get("probe_id") == probe_id:
                return "\n".join(out)
        out.append("")
    return "\n".join(out)


def post(body, key, timeout=300):
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://github.com/Dextergao14/REVOKE",
                 "X-Title": "REVOKE benchmark"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def extract(resp, item, salvage=False):
    """Pull the acted-on option out of a tool call, or out of JSON/plain text."""
    ch = (resp.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    for tc in (msg.get("tool_calls") or []):
        fn = tc.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        val = " ".join(str(v) for v in args.values()) if isinstance(args, dict) else str(args)
        if val.strip():
            return fn.get("name") or item["act_tool"], val.strip(), msg.get("content") or ""
    text = (msg.get("content") or "").strip()
    if not text:
        # An unfinished reasoning trace is not a decision.  Salvaging a name
        # from it would score the model on something it never committed to, so
        # this is only used when every retry has failed, and the report keeps
        # such answers out of the headline numbers.
        if salvage:
            reason = (msg.get("reasoning") or "").strip()
            if reason:
                names = sorted(item["entity_names"].values(), key=len, reverse=True)
                for n in names:
                    if n in reason[-600:]:
                        return item["act_tool"], n, "[recovered from reasoning]"
        return None, "", ""
    blob = text
    if "{" in text and "}" in text:
        try:
            j = json.loads(text[text.index("{"):text.rindex("}") + 1])
            if isinstance(j, dict) and j:
                blob = " ".join(str(v) for v in j.values())
        except Exception:                                     # noqa: BLE001
            pass
    return item["act_tool"], blob, text


def run_probe(item, probe, model, key, tries=5, max_tokens=16000):
    tools = [{"type": "function", "function": {
        "name": t["name"], "description": t["doc"],
        "parameters": {"type": "object",
                       "properties": {k: {"type": "string"} for k in t["params"]},
                       "required": list(t["params"])}}} for t in item["tools"]]
    convo = render(item, probe["probe_id"])
    sys_msg = SYSTEM.format(domain=item["domain"], act=item["act_tool"])
    # reasoning models spend the whole completion budget thinking and emit
    # nothing if it is tight, so give room and cap the reasoning effort
    base = {"model": model, "temperature": 0, "max_tokens": max_tokens,
            "reasoning": {"effort": "low"}}
    last_err = ""
    for attempt in range(tries):
        use_tools = attempt < 2
        if attempt >= 2:
            # a reasoning model that produced nothing was starved of output
            # budget, not confused; give it more room rather than guessing from
            # a truncated thought stream
            base["max_tokens"] = max_tokens * 2
            base.pop("reasoning", None)
        tail = (USER_TAIL.format(act=item["act_tool"]) if use_tools
                else JSON_TAIL.format(param=item["act_param"]))
        body = dict(base, messages=[{"role": "system", "content": sys_msg},
                                    {"role": "user", "content": convo + tail}])
        if use_tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        try:
            resp = post(body, key)
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read()[:180].decode(errors='replace')}"
            if e.code == 402:
                # OpenRouter blocks concurrent requests whose potential cost
                # exceeds the remaining balance; back off hard and retry
                time.sleep(8 + 6 * attempt + random.random() * 4)
                continue
            if e.code in (400, 404, 422):
                # some models reject `tools` or `reasoning`; drop them and retry
                base.pop("reasoning", None)
                if use_tools:
                    continue
            time.sleep(2 ** attempt + random.random())
            continue
        except Exception as e:                                 # noqa: BLE001
            last_err = f"{type(e).__name__}: {str(e)[:150]}"
            time.sleep(2 ** attempt + random.random())
            continue
        name, val, text = extract(resp, item, salvage=(attempt == tries - 1))
        if val:
            u = resp.get("usage") or {}
            return {"probe_id": probe["probe_id"],
                    "tool_calls": [{"name": name, "arguments": {item["act_param"]: val}}],
                    "text": text[:400],
                    "usage": {"in": u.get("prompt_tokens", 0), "out": u.get("completion_tokens", 0),
                              "cost": (resp.get("usage") or {}).get("cost", 0)}}
        last_err = "no action in response"
    return {"probe_id": probe["probe_id"], "tool_calls": [], "text": "", "error": last_err}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blind", required=True)
    ap.add_argument("--models", required=True, help="comma-separated OpenRouter model ids")
    ap.add_argument("--out", required=True)
    ap.add_argument("--last", type=int, default=0, help="only the last N probes of each item")
    ap.add_argument("--items", default="", help="comma-separated item ids (default: all)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=16000)
    ap.add_argument("--key", default=os.environ.get("OPENROUTER_API_KEY"))
    a = ap.parse_args()
    if not a.key:
        sys.exit("set OPENROUTER_API_KEY")
    if "full" in os.path.basename(a.blind):
        sys.exit("refusing: that file name suggests it carries ground truth")

    items = [json.loads(l) for l in open(a.blind)]
    if a.items:
        keep = set(a.items.split(","))
        items = [i for i in items if i["id"] in keep]
    if any("licensed" in p for i in items for p in i["probes"]):
        sys.exit("refusing: dataset carries ground truth")
    os.makedirs(a.out, exist_ok=True)
    lock = threading.Lock()

    for model in a.models.split(","):
        model = model.strip()
        path = os.path.join(a.out, model.replace("/", "__").replace(":", "_") + ".jsonl")
        done = set()
        if os.path.exists(path):
            for line in open(path):
                r = json.loads(line)
                done |= {s["probe_id"] for s in r.get("steps", [])}
        jobs = []
        for it in items:
            ps = it["probes"][-a.last:] if a.last else it["probes"]
            jobs += [(it, p) for p in ps if p["probe_id"] not in done]
        if not jobs:
            print(f"{model}: already complete")
            continue
        t0 = time.time()
        got = {}
        errs = 0
        # write each probe as it lands, so a killed run is resumable and the
        # progress is visible from outside
        sink = open(path + ".part", "a")
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            futs = {ex.submit(run_probe, it, p, model, a.key, 5, a.max_tokens): (it, p)
                    for it, p in jobs}
            for n, f in enumerate(as_completed(futs), 1):
                it, p = futs[f]
                try:
                    res = f.result()
                except Exception as e:                          # noqa: BLE001
                    res = {"probe_id": p["probe_id"], "tool_calls": [], "error": str(e)[:150]}
                errs += bool(res.get("error"))
                with lock:
                    got.setdefault(it["id"], []).append(res)
                    sink.write(json.dumps({"id": it["id"], "model": model, "steps": [res]}) + "\n")
                    sink.flush()
                if n % 5 == 0 or n == len(jobs):
                    print(f"  {model}: {n}/{len(jobs)}  errors={errs}  "
                          f"{time.time() - t0:.0f}s", flush=True)
        sink.close()
        with open(path, "a") as f:
            for iid, steps in got.items():
                steps.sort(key=lambda s: int(s["probe_id"].split("#p")[1]))
                f.write(json.dumps({"id": iid, "model": model, "steps": steps}) + "\n")
        os.remove(path + ".part")
        cost = sum(s.get("usage", {}).get("cost", 0) or 0 for v in got.values() for s in v)
        tin = sum(s.get("usage", {}).get("in", 0) for v in got.values() for s in v)
        print(f"{model}: {len(jobs)} probes, {errs} errors, {tin/1000:.0f}k input tokens, "
              f"${cost:.3f}, {time.time() - t0:.0f}s -> {path}", flush=True)


if __name__ == "__main__":
    main()
