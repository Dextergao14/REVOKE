#!/usr/bin/env python3
"""Print the transcript of a *blind* item up to and including one probe turn,
with the agent's own earlier replies interleaved.  This is the only view an
agent under test needs; it never touches a file that carries ground truth.

  python scripts/render_context.py --blind <blind.jsonl> --id <item id> \
      --probe <probe id> [--answers '{"<probe id>": "<reply>", ...}'] [--window K]
"""
import argparse, json, sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blind", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--probe", required=True)
    ap.add_argument("--answers", default="{}")
    ap.add_argument("--answers-b64", default="", help="base64 of the answers JSON (avoids shell quoting)")
    ap.add_argument("--window", type=int, default=0, help="only the last K sessions (0 = all)")
    a = ap.parse_args()
    if "full" in a.blind.rsplit("/", 1)[-1]:
        sys.exit("refusing: this file name suggests it carries ground truth")
    item = next((json.loads(l) for l in open(a.blind) if json.loads(l)["id"] == a.id), None)
    if item is None:
        sys.exit(f"no item {a.id}")
    import base64
    answers = json.loads(base64.b64decode(a.answers_b64).decode() if a.answers_b64 else a.answers)
    target = next(s["index"] for s in item["sessions"] for t in s["turns"] if t.get("probe_id") == a.probe)
    lo = target - a.window + 1 if a.window else 0
    out = []
    for s in item["sessions"]:
        if s["index"] > target or s["index"] < lo:
            continue
        out.append(f"[Session {s['index']}]")
        for t in s["turns"]:
            out.append(t["text"])
            pid = t.get("probe_id")
            if pid == a.probe:
                print("\n".join(out))
                return
            if pid and pid in answers:
                out.append(f"you: {answers[pid]}")
        out.append("")
    print("\n".join(out))


if __name__ == "__main__":
    main()
