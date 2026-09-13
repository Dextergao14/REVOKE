#!/usr/bin/env python3
"""Render long-tier episodes as browsable HTML for inspection by the authors.

    python3 scripts/episode_viewer.py --full data/long/long_full.jsonl --out /tmp/viewer

Writes one page per episode plus index.html.  The page shows the transcript as
the agent sees it, with a toggle that reveals what only the grader knows: turn
kinds (rule / noise / filler), and for every task its option set, the licensed
and violating options and the rules that make them so.  Never hand these pages
to a system under test.
"""
from __future__ import annotations

import argparse
import gzip
import html
import json
import os

CSS = """
:root{--bg:#f6f5f1;--sheet:#fffdf8;--ink:#1c1b18;--ink2:#5a5750;--mute:#8d8a82;--rule:#ddd9d0;--acc:#2a5d8f;
--upd:#fff2c9;--upd-b:#d9a800;--noise:#fbe4e4;--noise-b:#c65a5a;--probe:#e2eef9;--probe-b:#2a5d8f;--lic:#1d6b3a;--vio:#b3261e;--mono:ui-monospace,Menlo,Consolas,monospace;--sans:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#141412;--sheet:#1c1c19;--ink:#ecebe6;--ink2:#b5b2aa;--mute:#7f7c74;--rule:#33322e;--acc:#7fb0e0;--upd:#3a3110;--upd-b:#d9a800;--noise:#3a1f1f;--noise-b:#d07070;--probe:#152a3d;--probe-b:#7fb0e0;--lic:#7fd49a;--vio:#ff8a80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 var(--sans)}
header{position:sticky;top:0;background:var(--sheet);border-bottom:1px solid var(--rule);padding:10px 20px;display:flex;gap:18px;align-items:center;flex-wrap:wrap;z-index:2}
header h1{font-size:15px;margin:0;font-weight:600}header .m{color:var(--ink2);font-size:13px}header label{font-size:13px;color:var(--ink2);cursor:pointer}
.wrap{display:grid;grid-template-columns:220px 1fr;gap:0;max-width:1400px;margin:0 auto}
nav{position:sticky;top:52px;height:calc(100vh - 52px);overflow:auto;padding:12px 10px;border-right:1px solid var(--rule);font-size:12px}
nav a{display:block;color:var(--ink2);text-decoration:none;padding:2px 6px;border-radius:3px;font-variant-numeric:tabular-nums}
nav a.p{color:var(--acc);font-weight:600}nav a:hover{background:var(--probe)}
main{padding:16px 28px 80px;min-width:0}
.sess{margin:0 0 22px;border-top:1px solid var(--rule);padding-top:10px}
.sess h2{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);margin:0 0 6px;font-weight:600}
.t{padding:3px 8px;margin:1px 0;border-left:3px solid transparent;white-space:pre-wrap;word-break:break-word;color:var(--ink)}
.t.meta{color:var(--mute);font-style:italic}.t.pad{color:var(--ink2)}
body.gt .t.update{background:var(--upd);border-left-color:var(--upd-b)}
body.gt .t.noise{background:var(--noise);border-left-color:var(--noise-b)}
body.gt .t.notice{background:var(--upd);border-left-color:var(--upd-b);font-weight:500}
.t.probe{background:var(--probe);border-left-color:var(--probe-b);font-weight:500}
.gtbox{display:none;margin:4px 0 10px 11px;padding:8px 12px;border:1px dashed var(--probe-b);font-family:var(--mono);font-size:12px;color:var(--ink2);white-space:pre-wrap}
body.gt .gtbox{display:block}.gtbox .l{color:var(--lic);font-weight:600}.gtbox .v{color:var(--vio);font-weight:600}
.legend{display:none;gap:14px;font-size:12px;color:var(--ink2)}body.gt .legend{display:flex}
.sw{display:inline-block;width:10px;height:10px;margin-right:4px;vertical-align:-1px;border-radius:2px}
table.idx{border-collapse:collapse;font-size:13px;margin:20px}table.idx td,table.idx th{padding:6px 12px;border-bottom:1px solid var(--rule);text-align:left;font-variant-numeric:tabular-nums}
table.idx th{font-weight:600}table.idx a{color:var(--acc)}
"""


def load(path):
    opener = gzip.open if path.endswith(".gz") else open
    return [json.loads(l) for l in opener(path, "rt")]


def render(item) -> str:
    m = item["meta"]
    pm = {p["probe_id"]: p for p in item["probes"]}
    names = item["entity_names"]
    n_probe_sessions = {p["session"] for p in item["probes"]}
    out = [f"<meta charset='utf-8'><title>{html.escape(item['id'])}</title><style>{CSS}</style>",
           f"<header><h1>{html.escape(item['id'])}</h1><span class='m'>{html.escape(item['domain_title'])} · "
           f"{m['format']} · {m['tokens'] // 1000}k tokens · {item['n_sessions']} sessions · {len(item['probes'])} tasks</span>"
           f"<label><input type='checkbox' id='gt'> show ground truth (author view)</label>"
           f"<span class='legend'><span><i class='sw' style='background:var(--upd-b)'></i>rule</span>"
           f"<span><i class='sw' style='background:var(--noise-b)'></i>noise</span>"
           f"<span><i class='sw' style='background:var(--probe-b)'></i>task</span></span>"
           f"<a class='m' href='index.html'>all episodes</a></header>",
           "<div class='wrap'><nav>"]
    for s in item["sessions"]:
        cls = " class='p'" if s["index"] in n_probe_sessions else ""
        out.append(f"<a href='#s{s['index']}'{cls}>session {s['index']}{' · task' if cls else ''}</a>")
    out.append("</nav><main>")
    for s in item["sessions"]:
        out.append(f"<section class='sess' id='s{s['index']}'><h2>Session {s['index']}</h2>")
        for t in s["turns"]:
            k = t.get("kind", "")
            out.append(f"<div class='t {html.escape(k)}'>{html.escape(t['text'])}</div>")
            pid = t.get("probe_id")
            if pid and pid in pm:
                p = pm[pid]
                d = p.get("difficulty", {})
                lic = ", ".join(names[e] for e in p["licensed"]) or "(none)"
                vio = "; ".join(f"{names[e]} ← {', '.join(p['blamed'].get(e, []))}" for e in p["violating"]) or "(none)"
                trap = ", ".join(names[e] for e in p["stale_trap"]) or "-"
                out.append(f"<div class='gtbox'>{html.escape(pid)}  tests={p['tests']}  weight={d.get('weight')}  "
                           f"recall_span={d.get('recall_span')} ({d.get('span_tier')})  n_violating={len(p['violating'])}\n"
                           f"<span class='l'>licensed:</span> {html.escape(lic)}\n<span class='v'>violating:</span> {html.escape(vio)}\n"
                           f"stale trap: {html.escape(trap)}   facts: {html.escape(', '.join(f for f in p.get('facts', []) if not f.startswith('uncert')) or '-')}</div>")
        out.append("</section>")
    out.append("</main></div><script>const c=document.getElementById('gt');c.onchange=()=>document.body.classList.toggle('gt',c.checked);</script>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    items = load(a.full)
    rows = []
    for it in items:
        fn = f"{it['id']}.html"
        open(os.path.join(a.out, fn), "w").write(render(it))
        m = it["meta"]
        rows.append(f"<tr><td><a href='{fn}'>{html.escape(it['id'])}</a></td><td>{html.escape(it['domain_title'])}</td>"
                    f"<td>{m['format']}</td><td>{m['tokens'] // 1000}k</td><td>{it['n_sessions']}</td><td>{len(it['probes'])}</td>"
                    f"<td>{sum(1 for p in it['probes'] if p['stale_trap'])}</td>"
                    f"<td>{sum(1 for p in it['probes'] if p['difficulty']['span_tier'] == 'far')}</td></tr>")
    open(os.path.join(a.out, "index.html"), "w").write(
        f"<meta charset='utf-8'><title>REVOKE long-tier episodes</title><style>{CSS}</style><header><h1>REVOKE long-tier episodes</h1>"
        f"<span class='m'>{len(items)} episodes · author view; never hand these pages to a system under test</span></header>"
        f"<table class='idx'><tr><th>episode</th><th>world</th><th>layout</th><th>tokens</th><th>sessions</th><th>tasks</th><th>traps</th><th>far span</th></tr>"
        + "".join(rows) + "</table>")
    print(f"{len(items)} pages -> {a.out}/index.html")


if __name__ == "__main__":
    main()
