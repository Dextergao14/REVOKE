#!/usr/bin/env python3
"""Leak audit for a workflow run: every Bash/Read call each subagent made, flagged
if it touched anything other than the sanctioned render command."""
import glob, json, re, sys, collections
d = sys.argv[1]
ok = re.compile(r"render_context\.py .*--blind .*pilot_blind\.jsonl")
flag = collections.Counter(); calls = 0; agents = 0; bad = []
for f in glob.glob(f"{d}/agent-*.jsonl"):
    agents += 1
    for line in open(f):
        try: r = json.loads(line)
        except Exception: continue
        msg = r.get("message", r)
        for blk in (msg.get("content") or []) if isinstance(msg, dict) else []:
            if isinstance(blk, dict) and blk.get("type") == "tool_use":
                name = blk.get("name", ""); inp = blk.get("input", {})
                if name in ("Bash", "Read", "Grep", "Glob", "Edit", "Write"):
                    calls += 1
                    s = json.dumps(inp)
                    if not (name == "Bash" and ok.search(s)):
                        flag[name] += 1; bad.append((f.split("/")[-1], name, s[:160]))
print(f"agents {agents}, file/shell tool calls {calls}, off-script {sum(flag.values())} {dict(flag)}")
for b in bad[:15]: print("  ", b)
