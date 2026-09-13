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


STR = {
 "en": {"gt": "show ground truth (author view)", "rule": "rule", "noise": "noise", "task": "task", "all": "all episodes",
        "tokens": "tokens", "sessions": "sessions", "tasks": "tasks", "session": "Session", "task_mark": " · task",
        "licensed": "licensed:", "violating": "violating:", "trap": "stale trap:", "facts": "facts:", "weight": "weight",
        "span": "recall_span", "nviol": "n_violating", "title": "REVOKE long-tier episodes",
        "sub": "author view; never hand these pages to a system under test",
        "cols": ["episode", "world", "layout", "tokens", "sessions", "tasks", "traps", "far span"],
        "layout": {"sectioned": "sectioned", "flat": "flat"}},
 "zh": {"gt": "显示 ground truth（作者视图）", "rule": "规则", "noise": "闲话 / 近似决议", "task": "题目", "all": "全部 episode",
        "tokens": "token", "sessions": "场", "tasks": "题", "session": "第 {n} 场", "task_mark": " · 题",
        "licensed": "合法选项：", "violating": "违规选项 ← 依据规则：", "trap": "陷阱（上次合法、现在违规）：", "facts": "本题附加事实：",
        "weight": "权重", "span": "回忆跨度", "nviol": "违规选项数", "title": "REVOKE 长程 episode",
        "sub": "作者视图；绝不能把这些页面给被测模型",
        "cols": ["episode", "场景", "版式", "token", "场次", "题数", "陷阱题", "远距题"],
        "layout": {"sectioned": "分节纪要", "flat": "聊天流"}},
}
WORLD_ZH = {"Long-stay ward: rounds and nursing handover": "长期住院病房：查房与护理交班",
            "Release pipeline governance: #platform-release channel": "发布流水线治理：#platform-release 频道",
            "Product design org: crit notes and design-system decisions": "产品设计团队：评审记录与设计系统决议",
            "Companion app: one person and their care circle": "陪伴应用：一位老人与她的照护圈",
            "Live-service game: narrative and quest content review": "长线运营游戏：叙事与任务内容评审",
            "Tooling and vendor governance (company minute book)": "工具与供应商治理（公司会议纪要）"}
TESTS_ZH = {"ADD": "新增许可", "ADD_BAN": "新增禁令", "CONFLICT": "冲突（按权威裁决）", "SUPERSEDE": "替换/撤销", "CONDITION": "条件化",
            "SUPPORT": "重申提级", "RETRACT": "部分撤回", "NOISE": "噪声题", "CANARY": "对照题"}
TIER_ZH = {"near": "近", "mid": "中", "far": "远"}


def load(path):
    opener = gzip.open if path.endswith(".gz") else open
    return [json.loads(l) for l in opener(path, "rt")]


def render(item, lang: str = "en") -> str:
    T = STR[lang]
    m = item["meta"]
    pm = {p["probe_id"]: p for p in item["probes"]}
    names = item["entity_names"]
    n_probe_sessions = {p["session"] for p in item["probes"]}
    world = item["domain_title"] if lang == "en" else WORLD_ZH.get(item["domain_title"], item["domain_title"])
    layout = T["layout"].get(m["format"], m["format"])
    sess_label = (lambda n: f"{T['session']} {n}") if lang == "en" else (lambda n: T["session"].format(n=n))
    out = [f"<meta charset='utf-8'><title>{html.escape(item['id'])}</title><style>{CSS}</style>",
           f"<header><h1>{html.escape(item['id'])}</h1><span class='m'>{html.escape(world)} · "
           f"{layout} · {m['tokens'] // 1000}k {T['tokens']} · {item['n_sessions']} {T['sessions']} · {len(item['probes'])} {T['tasks']}</span>"
           f"<label><input type='checkbox' id='gt'> {T['gt']}</label>"
           f"<span class='legend'><span><i class='sw' style='background:var(--upd-b)'></i>{T['rule']}</span>"
           f"<span><i class='sw' style='background:var(--noise-b)'></i>{T['noise']}</span>"
           f"<span><i class='sw' style='background:var(--probe-b)'></i>{T['task']}</span></span>"
           f"<a class='m' href='index.html'>{T['all']}</a></header>",
           "<div class='wrap'><nav>"]
    for s in item["sessions"]:
        cls = " class='p'" if s["index"] in n_probe_sessions else ""
        out.append(f"<a href='#s{s['index']}'{cls}>{sess_label(s['index'])}{T['task_mark'] if cls else ''}</a>")
    out.append("</nav><main>")
    for s in item["sessions"]:
        out.append(f"<section class='sess' id='s{s['index']}'><h2>{sess_label(s['index'])}</h2>")
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
                tests = p["tests"] if lang == "en" else f"{p['tests']}（{TESTS_ZH.get(p['tests'], p['tests'])}）"
                tier = d.get("span_tier") if lang == "en" else TIER_ZH.get(d.get("span_tier"), d.get("span_tier"))
                out.append(f"<div class='gtbox'>{html.escape(pid)}  {T['nviol'] if False else 'tests'}={html.escape(str(tests))}  {T['weight']}={d.get('weight')}  "
                           f"{T['span']}={d.get('recall_span')} ({tier})  {T['nviol']}={len(p['violating'])}\n"
                           f"<span class='l'>{T['licensed']}</span> {html.escape(lic)}\n<span class='v'>{T['violating']}</span> {html.escape(vio)}\n"
                           f"{T['trap']} {html.escape(trap)}   {T['facts']} {html.escape(', '.join(f for f in p.get('facts', []) if not f.startswith('uncert')) or '-')}</div>")
        out.append("</section>")
    out.append("</main></div><script>const c=document.getElementById('gt');c.onchange=()=>document.body.classList.toggle('gt',c.checked);</script>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="en", choices=("en", "zh"), help="language of the viewer chrome and annotations")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    items = load(a.full)
    T = STR[a.lang]
    rows = []
    for it in items:
        fn = f"{it['id']}.html"
        open(os.path.join(a.out, fn), "w").write(render(it, a.lang))
        m = it["meta"]
        world = it["domain_title"] if a.lang == "en" else WORLD_ZH.get(it["domain_title"], it["domain_title"])
        rows.append(f"<tr><td><a href='{fn}'>{html.escape(it['id'])}</a></td><td>{html.escape(world)}</td>"
                    f"<td>{T['layout'].get(m['format'], m['format'])}</td><td>{m['tokens'] // 1000}k</td><td>{it['n_sessions']}</td><td>{len(it['probes'])}</td>"
                    f"<td>{sum(1 for p in it['probes'] if p['stale_trap'])}</td>"
                    f"<td>{sum(1 for p in it['probes'] if p['difficulty']['span_tier'] == 'far')}</td></tr>")
    open(os.path.join(a.out, "index.html"), "w").write(
        f"<meta charset='utf-8'><title>{T['title']}</title><style>{CSS}</style><header><h1>{T['title']}</h1>"
        f"<span class='m'>{len(items)} episodes · {T['sub']}</span></header>"
        f"<table class='idx'><tr>" + "".join(f"<th>{c}</th>" for c in T["cols"]) + "</tr>"
        + "".join(rows) + "</table>")
    print(f"{len(items)} pages -> {a.out}/index.html")


if __name__ == "__main__":
    main()
