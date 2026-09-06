#!/usr/bin/env python3
"""Render trial_data.json (from trial_analysis.py) as a self-contained HTML figure."""
import argparse, json, html

STRINGS = {
 "en": {
  "title": "One Episode, Four Memories",
  "h2_fig": "What the world said, and what each agent did",
  "lede_fig": "Top: for every drug offered in this episode, whether the current constraint closure <em>licenses</em> it (green wash), <em>forbids</em> it (red wash) or says nothing (blank), session by session. Chips on the rail mark the events that changed the closure; outlined cells are the options offered at each probe. Bottom, aligned to the same columns: the drug each memory condition administered, coloured by the verdict the grader gave that action. Hover any decision for the agent's own reasoning.",
  "lg_lic": "licensed", "lg_forb": "forbidden", "lg_sil": "silent (never mentioned)", "lg_off": "offered at this probe",
  "lg_good": "✓ compliant &amp; completes the task", "lg_crit": "✕ violation — episode fails", "lg_warn": "○ safe but unlicensed — task not completed",
  "lg_trap": "⚠ stale trap: this option was compliant at the previous probe",
  "h2_tbl": "Trace table",
  "lede_tbl": "One row per graded decision. Evidence = the sessions the agent said it relied on. Beliefs = the agent's stated status for each offered option, marked against the closure.",
  "aria": "Constraint timeline and agent decisions",
  "sub": "{dom} · episode {id} · {ns} sessions, {np} graded decisions, {nt} stale-memory traps · motifs {motifs}. {tail}",
  "sub_tail": "{nc} memory conditions run with the same backbone family; the grader re-derives every verdict from the event log.",
  "sub_tail0": "Ground truth only — no traces loaded.",
  "js": {
   "cond": {"full": "full context", "window": "window · last 3 sessions", "notes": "notes + last 3 sessions"},
   "session": "session", "probe": "probe", "decision": "decision", "context": "CONTEXT",
   "summary": "{nv} viol · {nc}/{np} done", "notraces": "No agent traces loaded.",
   "gave": "Administered", "v_good": "✓ compliant, task completed", "v_crit": "✕ violation", "v_warn": "○ safe but not licensed — task not completed",
   "trap": "took the stale trap", "stale_support": "stale support in D<sub>t</sub>", "closure": "Closure", "lic": "licensed", "forb": "forbidden",
   "reads": "Reads", "none": "none", "evidence": "Evidence sessions", "reasoning": "Reasoning.", "beliefs": "Beliefs.", "closure_says": "closure",
   "gt": {"licensed": "licensed", "forbidden": "forbidden", "silent": "silent"},
   "th": ["Condition", "Probe", "Session", "Tests", "Chose", "Verdict", "Closure said", "Evidence", "Reasoning"],
   "tv_good": "compliant", "tv_crit": "violation", "tv_warn": "unlicensed", "tv_trap": "stale trap",
   "t_lic": "lic", "t_forb": "forb", "notes_sum": "Scratchpad evolution (notes condition)", "after": "after session {s}", "task": " (task)"
  },
  "domains": {}
 },
 "zh": {
  "title": "一道题，四种记忆",
  "h2_fig": "世界说了什么，每个 agent 做了什么",
  "lede_fig": "上半部分：本题提供过的每一种药，在每个 session 时当前约束闭包是<em>许可</em>它（绿色）、<em>禁止</em>它（红色）还是没有提及（空白）。顶部 rail 上的标签是改变了闭包的事件；带框的格子是该 probe 提供的选项。下半部分对齐同一列：每种记忆条件实际给了哪种药，颜色是判分器对这个动作的裁定。把鼠标悬停在任意决策上可看到 agent 自己的推理。",
  "lg_lic": "许可", "lg_forb": "禁止", "lg_sil": "未提及（从未被说到）", "lg_off": "本 probe 提供的选项",
  "lg_good": "✓ 合规且完成任务", "lg_crit": "✕ 违规——整题作废", "lg_warn": "○ 安全但未被许可——任务未完成",
  "lg_trap": "⚠ 陈旧陷阱：该选项在上一次 probe 时还合规",
  "h2_tbl": "Trace 表",
  "lede_tbl": "每个被判分的决策一行。引用 = agent 自述依据的 session。信念 = agent 对每个选项给出的状态，与闭包逐项对照。",
  "aria": "约束时间线与 agent 决策",
  "sub": "{dom} · 题目 {id} · {ns} 个 session，{np} 个判分决策，{nt} 个陈旧记忆陷阱 · motif：{motifs}。{tail}",
  "sub_tail": "同一模型族下跑 {nc} 种记忆条件；判分器从事件日志重新推导每个裁定。",
  "sub_tail0": "仅真值——未加载 trace。",
  "js": {
   "cond": {"full": "全上下文", "window": "窗口 · 最近 3 个 session", "notes": "便签 + 最近 3 个 session"},
   "session": "session", "probe": "probe", "decision": "决策", "context": "CONTEXT",
   "summary": "{nv} 违规 · {nc}/{np} 完成", "notraces": "未加载 agent trace。",
   "gave": "给了", "v_good": "✓ 合规，任务完成", "v_crit": "✕ 违规", "v_warn": "○ 安全但未被许可——任务未完成",
   "trap": "踩了陈旧陷阱", "stale_support": "陈旧许可位于 D<sub>t</sub>", "closure": "闭包", "lic": "许可", "forb": "禁止",
   "reads": "只读调用", "none": "无", "evidence": "引用 session", "reasoning": "推理。", "beliefs": "信念。", "closure_says": "闭包",
   "gt": {"licensed": "许可", "forbidden": "禁止", "silent": "未提及"},
   "th": ["条件", "Probe", "Session", "测试事件", "选择", "裁定", "闭包", "引用", "推理（agent 原文）"],
   "tv_good": "合规", "tv_crit": "违规", "tv_warn": "未许可", "tv_trap": "陈旧陷阱",
   "t_lic": "许可", "t_forb": "禁止", "notes_sum": "便签演化（notes 条件）", "after": "第 {s} 个 session 之后", "task": "（任务）"
  },
  "domains": {"Platform API governance": "平台 API 治理", "Procurement compliance": "采购合规",
              "Medication constraint tracking (synthetic formulary)": "用药约束跟踪（合成药典）",
              "Household automation preferences": "家居自动化偏好", "Financial operation permissions": "金融操作权限"}
 }
}

TPL = r"""<meta charset="utf-8"><title>__TITLE__</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10);
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
  --good-wash:rgba(12,163,12,.13); --crit-wash:rgba(208,59,59,.13); --warn-wash:rgba(250,178,25,.18);
  --probe-col:rgba(11,11,11,.035); --chip:#efeeea; --chip-ink:#52514e;
  --ui:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',sans-serif; --mono:'IBM Plex Mono',ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
  --good-wash:rgba(12,163,12,.22); --crit-wash:rgba(208,59,59,.24); --warn-wash:rgba(250,178,25,.22);
  --probe-col:rgba(255,255,255,.05); --chip:#2a2a28; --chip-ink:#c3c2b7;
}}
:root[data-theme="dark"]{
  --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
  --good-wash:rgba(12,163,12,.22); --crit-wash:rgba(208,59,59,.24); --warn-wash:rgba(250,178,25,.22);
  --probe-col:rgba(255,255,255,.05); --chip:#2a2a28; --chip-ink:#c3c2b7;
}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font-family:var(--ui);font-size:14px;line-height:1.5}
.wrap{max-width:1260px;margin:0 auto;padding:28px 22px 64px}
h1{font-size:22px;font-weight:600;margin:0 0 4px;letter-spacing:-.01em;text-wrap:balance}
.sub{color:var(--ink-2);margin:0 0 6px;max-width:80ch}
.meta{font-family:var(--mono);font-size:12px;color:var(--muted);margin:0 0 18px}
.card{background:var(--surface);border:1px solid var(--ring);padding:18px 18px 14px;margin:0 0 18px}
.card h2{font-size:14px;font-weight:600;margin:0 0 2px;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-2)}
.card .lede{color:var(--ink-2);font-size:13px;margin:0 0 12px;max-width:90ch}
.legend{display:flex;flex-wrap:wrap;gap:8px 20px;font-size:12.5px;color:var(--ink-2);margin:0 0 12px;align-items:center}
.legend .k{display:inline-flex;align-items:center;gap:6px}
.sw{width:14px;height:14px;border-radius:3px;display:inline-block;border:1px solid var(--ring)}
.dot{width:12px;height:12px;border-radius:50%;display:inline-block;border:2px solid var(--surface);box-shadow:0 0 0 1px var(--ring)}
.scroll{overflow-x:auto}
svg{display:block;font-family:var(--ui)}
svg text{fill:var(--ink-2);font-size:11.5px}
svg .lbl{fill:var(--ink);font-size:12px}
svg .mut{fill:var(--muted);font-size:11px}
svg .mono{font-family:var(--mono)}
svg .grid{stroke:var(--grid);stroke-width:1}
svg .axis{stroke:var(--axis);stroke-width:1}
svg .band-good{fill:var(--good-wash)} svg .band-crit{fill:var(--crit-wash)}
svg .probecol{fill:var(--probe-col)}
svg .optring{fill:none;stroke:var(--ink-2);stroke-width:1;stroke-opacity:.55}
svg .chip{fill:var(--chip)} svg .chip-t{fill:var(--chip-ink);font-size:10px;font-weight:500;letter-spacing:.04em}
svg .mk-good{fill:var(--good)} svg .mk-crit{fill:var(--crit)} svg .mk-warn{fill:var(--warn)}
svg .mk-ring{stroke:var(--surface);stroke-width:2}
svg .mk-glyph{fill:#fff;font-size:10px;font-weight:600;text-anchor:middle;dominant-baseline:central;pointer-events:none}
svg .mk-glyph.dark{fill:#0b0b0b}
svg .cell-name{fill:var(--ink);font-size:10.5px;text-anchor:middle;font-weight:500;letter-spacing:-.01em}
svg .hit{fill:transparent;cursor:default}
svg .hl{fill:none;stroke:var(--ink);stroke-width:1.5;stroke-opacity:.9;pointer-events:none}
.tip{position:fixed;z-index:9;max-width:420px;background:var(--surface);color:var(--ink);border:1px solid var(--ring);box-shadow:0 6px 24px rgba(0,0,0,.14);padding:10px 12px;font-size:12.5px;line-height:1.45;pointer-events:none;display:none}
.tip b{font-weight:600}
.tip .m{font-family:var(--mono);font-size:11px;color:var(--muted)}
.tip .r{margin-top:6px;color:var(--ink-2)}
.tip ul{margin:4px 0 0;padding-left:16px}
table{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums}
th{text-align:left;font-weight:600;padding:8px 10px;border-bottom:1px solid var(--axis);color:var(--ink);white-space:nowrap;vertical-align:bottom}
td{padding:8px 10px;border-bottom:1px solid var(--grid);vertical-align:top;color:var(--ink-2)}
td.n{color:var(--ink);font-weight:500;white-space:nowrap}
td .st{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.pill{display:inline-block;font-family:var(--mono);font-size:11px;padding:1px 6px;border-radius:3px;background:var(--chip);color:var(--chip-ink)}
.reason{max-width:62ch}
details{margin-top:10px} summary{cursor:pointer;color:var(--ink-2);font-size:13px}
.notes{font-family:var(--mono);font-size:11.5px;white-space:pre-wrap;background:var(--chip);padding:10px 12px;margin:8px 0 0;color:var(--ink)}
:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
</style>
<div class="wrap">
<h1>__H1__</h1>
<p class="sub">__SUB__</p>
<p class="meta">__META__</p>

<div class="card">
<h2>__H2_FIG__</h2>
<p class="lede">__LEDE_FIG__</p>
<div class="legend">
  <span class="k"><span class="sw" style="background:var(--good-wash)"></span>__LG_LIC__</span>
  <span class="k"><span class="sw" style="background:var(--crit-wash)"></span>__LG_FORB__</span>
  <span class="k"><span class="sw" style="background:var(--surface)"></span>__LG_SIL__</span>
  <span class="k"><span class="sw" style="background:none;border:1px solid var(--ink-2)"></span>__LG_OFF__</span>
  <span class="k"><span class="dot" style="background:var(--good)"></span>__LG_GOOD__</span>
  <span class="k"><span class="dot" style="background:var(--crit)"></span>__LG_CRIT__</span>
  <span class="k"><span class="dot" style="background:var(--warn)"></span>__LG_WARN__</span>
  <span class="k">__LG_TRAP__</span>
</div>
<div class="scroll"><svg id="fig" role="img" aria-label="__ARIA__"></svg></div>
</div>

<div class="card">
<h2>__H2_TBL__</h2>
<p class="lede">__LEDE_TBL__</p>
<div class="scroll"><table id="tbl"></table></div>
<div id="notes"></div>
</div>
</div>
<div class="tip" id="tip"></div>
<script id="data" type="application/json">__DATA__</script>
<script id="strings" type="application/json">__STRINGS__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const T = JSON.parse(document.getElementById('strings').textContent);
const fmt = (t, o) => t.replace(/\{(\w+)\}/g, (_, k) => o[k]);
const N = Object.fromEntries(D.ground_truth.entities.map(e => [e.id, e.name]));
const probeSessions = new Set(D.probes.map(p => p.session));
const offeredIds = new Set(D.probes.flatMap(p => p.options));
// rows: group by the motif that introduced the drug; distractors last
const introducedBy = {};
for (const ev of D.ground_truth.events) for (const id of Object.keys(N)) if (ev.text.includes(N[id]) && !introducedBy[id]) introducedBy[id] = ev.motif;
const rows = D.ground_truth.entities.filter(e => offeredIds.has(e.id))
  .sort((a, b) => (introducedBy[a.id] || 'zz').localeCompare(introducedBy[b.id] || 'zz') || N[a.id].localeCompare(N[b.id]));
const S = D.item.n_sessions;
const conds = D.conditions;
const condLabel = c => (T.cond[c.mode] || c.mode) + (c.model !== 'session' ? ' · ' + c.model : '');

// ---- geometry
const L = 120, R = 24, colW = 56, rowH = 22, railH = 50, gapY = 34, decRowH = 44, topPad = 8;
const groups = []; let lastM = null;
rows.forEach((e, i) => { const m = introducedBy[e.id] || 'zz'; if (m !== lastM) { groups.push(i); lastM = m; } });
const rowY = i => topPad + railH + i * rowH + groups.filter(g => g > 0 && g <= i).length * 6;
const gridBottom = rowY(rows.length - 1) + rowH;
const decTop = gridBottom + 26 + gapY;
const H = decTop + conds.length * decRowH + 34;
const W = L + colW * S + R;
const X = s => L + (s - 1) * colW;

const svg = document.getElementById('fig');
svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('width', W); svg.setAttribute('height', H); svg.style.minWidth = W + 'px';
const el = (t, a = {}, txt) => { const n = document.createElementNS('http://www.w3.org/2000/svg', t); for (const k in a) n.setAttribute(k, a[k]); if (txt != null) n.textContent = txt; svg.appendChild(n); return n; };
const tip = document.getElementById('tip');
const show = (html, ev) => { tip.innerHTML = html; tip.style.display = 'block'; move(ev); };
const move = ev => { const w = tip.offsetWidth, h = tip.offsetHeight; let x = ev.clientX + 14, y = ev.clientY + 14; if (x + w > innerWidth - 8) x = ev.clientX - w - 14; if (y + h > innerHeight - 8) y = ev.clientY - h - 14; tip.style.left = x + 'px'; tip.style.top = y + 'px'; };
const hide = () => tip.style.display = 'none';
const hover = (n, html) => { n.addEventListener('mouseenter', e => show(html, e)); n.addEventListener('mousemove', move); n.addEventListener('mouseleave', hide); n.setAttribute('tabindex', '0'); n.addEventListener('focus', e => { const r = n.getBoundingClientRect(); show(html, {clientX: r.left + r.width / 2, clientY: r.bottom}); }); n.addEventListener('blur', hide); };
const esc = s => String(s ?? '').replace(/[&<>]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]));

// probe columns
for (const p of D.probes) el('rect', {x: X(p.session), y: topPad + railH - 4, width: colW, height: gridBottom - (topPad + railH - 4) + 22, class: 'probecol'});
// bands
const tl = Object.fromEntries(D.ground_truth.timeline.map(r => [r.session, r.status]));
rows.forEach((e, i) => {
  for (let s = 1; s <= S; s++) {
    const st = tl[s][e.id];
    if (st === 'licensed' || st === 'forbidden') el('rect', {x: X(s) + 1, y: rowY(i) + 2, width: colW - 2, height: rowH - 4, class: st === 'licensed' ? 'band-good' : 'band-crit'});
  }
  el('text', {x: L - 10, y: rowY(i) + rowH / 2 + 4, 'text-anchor': 'end', class: 'lbl'}, N[e.id]);
  el('line', {x1: L, x2: X(S) + colW, y1: rowY(i) + rowH, y2: rowY(i) + rowH, class: 'grid'});
});
// offered options
for (const p of D.probes) for (const id of p.options) { const i = rows.findIndex(r => r.id === id); if (i >= 0) el('rect', {x: X(p.session) + 1.5, y: rowY(i) + 2.5, width: colW - 3, height: rowH - 5, rx: 2, class: 'optring'}); }
// session axis (below the grid)
el('line', {x1: L, x2: X(S) + colW, y1: gridBottom + 0.5, y2: gridBottom + 0.5, class: 'axis'});
for (let s = 1; s <= S; s++) el('text', {x: X(s) + colW / 2, y: gridBottom + 14, 'text-anchor': 'middle', class: 'mut mono'}, s);
el('text', {x: L - 10, y: gridBottom + 14, 'text-anchor': 'end', class: 'mut'}, T.session);
// event rail: one chip per event kind in the session, stacked (max 2), context facts folded into the tooltip
const bySess = {}; for (const ev of D.ground_truth.events) (bySess[ev.session] ||= []).push(ev);
for (const s in bySess) {
  const evs = bySess[s].filter(e => !(e.tags || []).includes('context'));
  const kinds = [...new Set(evs.map(e => e.kind))];
  const labels = kinds.length ? kinds.slice(0, 2) : [T.context];
  const x = X(+s);
  labels.forEach((k, i) => {
    const y = topPad + 2 + i * 20;
    el('rect', {x: x + 2, y, width: colW - 4, height: 17, rx: 3, class: 'chip'});
    el('text', {x: x + colW / 2, y: y + 12, 'text-anchor': 'middle', class: 'chip-t'}, k + (i === 1 && kinds.length > 2 ? ' +' : ''));
  });
  el('line', {x1: x + colW / 2, x2: x + colW / 2, y1: topPad + 2 + labels.length * 20 - 3, y2: topPad + railH - 4, class: 'axis'});
  const h = el('rect', {x, y: topPad, width: colW, height: railH - 4, class: 'hit'});
  hover(h, `<b>Session ${s}</b><ul>${bySess[s].map(e => `<li><span class="m">${e.kind}</span> ${esc(e.text)}</li>`).join('')}</ul>`);
}
// probe labels under axis
for (const p of D.probes) {
  const trap = p.stale_trap.length > 0;
  el('text', {x: X(p.session) + colW / 2, y: gridBottom + 30, 'text-anchor': 'middle', class: 'lbl mono'}, p.probe_id.split('#')[1] + (trap ? ' ⚠' : ''));
}
el('text', {x: L - 10, y: gridBottom + 30, 'text-anchor': 'end', class: 'mut'}, T.probe);

// ---- decision matrix
const verdict = st => st && st.violation ? 'crit' : (st && st.completed ? 'good' : 'warn');
const glyph = v => ({good: '✓', crit: '✕', warn: '○'})[v];
conds.forEach((c, ci) => {
  const y = decTop + ci * decRowH;
  el('text', {x: L - 10, y: y + decRowH / 2 - 3, 'text-anchor': 'end', class: 'lbl'}, condLabel(c).split(' · ')[0]);
  if (condLabel(c).includes(' · ')) el('text', {x: L - 10, y: y + decRowH / 2 + 11, 'text-anchor': 'end', class: 'mut'}, condLabel(c).split(' · ').slice(1).join(' · '));
  el('line', {x1: L, x2: X(S) + colW, y1: y + decRowH, y2: y + decRowH, class: 'grid'});
  const sm = c.summary; const nv = c.steps.filter(s => s.probe_id && s.violation).length, nc = c.steps.filter(s => s.probe_id && s.completed).length, np = c.steps.filter(s => s.probe_id).length;
  el('text', {x: X(S) + colW + 6, y: y + decRowH / 2 - 3, class: 'lbl'}, sm.compliant_success ? 'CSR 1' : 'CSR 0');
  el('text', {x: X(S) + colW + 6, y: y + decRowH / 2 + 11, class: 'mut'}, fmt(T.summary, {nv, nc, np}));
  for (const st of c.steps) {
    if (!st.probe_id) continue;
    const p = D.probes.find(q => q.probe_id === st.probe_id); const x = X(p.session); const v = verdict(st);
    const cx = x + colW / 2, cy = y + 14;
    const g = el('g');
    el('circle', {cx, cy, r: 8, class: 'mk-' + v + ' mk-ring'});
    el('text', {x: cx, y: cy, class: 'mk-glyph' + (v === 'warn' ? ' dark' : '')}, glyph(v));
    const name = st.chosen ? N[st.chosen] : (st.action ? st.action.argument : '—');
    el('text', {x: cx, y: y + 35, class: 'cell-name'}, name.length > 10 ? name.slice(0, 9) + '…' : name);
    const beliefs = (st.option_beliefs || []).map(b => { const id = Object.keys(N).find(k => N[k].toLowerCase() === b.option.toLowerCase()); const gt = id ? tl[p.session][id] : '?'; const ok = (b.status === 'permitted' && gt === 'licensed') || (b.status === 'forbidden' && gt === 'forbidden') || (b.status === 'unknown' && gt === 'silent'); return `<li>${esc(b.option)}: <b>${esc(b.status)}</b> ${ok ? '✓' : `✗ (${T.closure_says}: ${T.gt[gt] || gt})`} — ${esc(b.because)}</li>`; }).join('');
    const hit = el('rect', {x: x, y: y + 1, width: colW, height: decRowH - 2, class: 'hit'});
    const hl1 = el('rect', {x: x + 0.5, y: y + 0.5, width: colW - 1, height: decRowH - 1, rx: 3, class: 'hl'}); hl1.style.display = 'none';
    const ri = rows.findIndex(r => r.id === st.chosen); let hl2 = null;
    if (ri >= 0) { hl2 = el('rect', {x: x + 0.5, y: rowY(ri) + 0.5, width: colW - 1, height: rowH - 1, rx: 3, class: 'hl'}); hl2.style.display = 'none'; }
    hover(hit, `<b>${esc(condLabel(c))}</b> · <span class="m">${esc(st.probe_id.split('#')[1])} · session ${p.session} · tests ${p.tests}</span>
      <div class="r"><b>${T.gave} ${esc(name)}</b> → ${v === 'good' ? T.v_good : v === 'crit' ? T.v_crit : T.v_warn}${st.took_stale_trap ? ` · <b>${T.trap}</b>` : ''}${st.stale_support && st.stale_support.length ? ` · ${T.stale_support}: ${esc(st.stale_support.join(', '))}` : ''}</div>
      <div class="r">${T.closure}: ${T.lic} ${esc(p.licensed.map(i => N[i]).join(', ') || '—')} · ${T.forb} ${esc(p.violating.map(i => N[i]).join(', ') || '—')}</div>
      <div class="r">${T.reads}: ${(st.read_calls || []).length ? esc(st.read_calls.map(r => r.name + '(' + r.argument + ')').join(', ')) : T.none} · ${T.evidence}: ${esc((st.evidence_sessions || []).join(', ') || '—')}</div>
      <div class="r"><b>${T.reasoning}</b> ${esc(st.reasoning)}</div>
      <div class="r"><b>${T.beliefs}</b><ul>${beliefs}</ul></div>`);
    hit.addEventListener('mouseenter', () => { hl1.style.display = ''; if (hl2) hl2.style.display = ''; });
    hit.addEventListener('mouseleave', () => { hl1.style.display = 'none'; if (hl2) hl2.style.display = 'none'; });
  }
});
if (!conds.length) el('text', {x: L, y: decTop + 16, class: 'mut'}, T.notraces);
el('text', {x: L - 10, y: decTop - 6, 'text-anchor': 'end', class: 'mut'}, T.decision);

// ---- table view
const tbl = document.getElementById('tbl');
let th = '<thead><tr>' + T.th.map(h => `<th>${h}</th>`).join('') + '</tr></thead><tbody>';
for (const c of conds) for (const st of c.steps) {
  if (!st.probe_id) continue;
  const p = D.probes.find(q => q.probe_id === st.probe_id); const v = verdict(st); const name = st.chosen ? N[st.chosen] : (st.action ? st.action.argument : '—');
  th += `<tr><td class="n">${esc(condLabel(c))}</td><td><span class="pill">${esc(st.probe_id.split('#')[1])}</span>${p.stale_trap.length ? ' ⚠' : ''}</td><td>${p.session}</td><td>${esc(p.tests)}</td><td class="n">${esc(name)}</td>
    <td><span class="st"><span class="dot" style="background:var(--${v})"></span>${glyph(v)} ${v === 'good' ? T.tv_good : v === 'crit' ? T.tv_crit : T.tv_warn}${st.took_stale_trap ? ' · ' + T.tv_trap : ''}</span></td>
    <td>${T.t_lic}: ${esc(p.licensed.map(i => N[i]).join(', ') || '—')}<br>${T.t_forb}: ${esc(p.violating.map(i => N[i]).join(', ') || '—')}</td><td>${esc((st.evidence_sessions || []).join(', ') || '—')}</td><td class="reason">${esc(st.reasoning)}</td></tr>`;
}
tbl.innerHTML = th + '</tbody>';
// scratchpad evolution for the notes condition
const notesC = conds.find(c => c.mode === 'notes');
if (notesC) {
  const box = document.getElementById('notes');
  let h = `<details><summary>${T.notes_sum}</summary>`;
  for (const st of notesC.steps) if (st.notes_after) h += `<div class="notes"><span style="color:var(--muted)">${fmt(T.after, {s: st.session})}${st.probe_id ? T.task : ''}</span>\n${esc(st.notes_after)}</div>`;
  box.innerHTML = h + '</details>';
}
</script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="en", choices=sorted(STRINGS))
    a = ap.parse_args()
    d = json.load(open(a.data))
    it = d["item"]
    R = STRINGS[a.lang]
    ncond = len(d["conditions"])
    n_traps = sum(1 for p in d["probes"] if p["stale_trap"])
    h1 = R["title"]
    tail = R["sub_tail"].format(nc=ncond) if ncond else R["sub_tail0"]
    sub = R["sub"].format(dom=R["domains"].get(it["domain_title"], it["domain_title"]), id=it["id"], ns=it["n_sessions"],
                          np=len(d["probes"]), nt=n_traps, motifs=", ".join(it["motifs"]), tail=tail)
    meta = " · ".join(f"{c['condition']}: CSR {int(c['summary']['compliant_success'])}" for c in d["conditions"]) or "—"
    page = TPL
    for k in ("h2_fig", "lede_fig", "lg_lic", "lg_forb", "lg_sil", "lg_off", "lg_good", "lg_crit", "lg_warn", "lg_trap", "h2_tbl", "lede_tbl", "aria"):
        page = page.replace("__" + k.upper() + "__", R[k])
    page = (page.replace("__TITLE__", html.escape(h1)).replace("__H1__", html.escape(h1)).replace("__SUB__", html.escape(sub))
            .replace("__META__", html.escape(meta)).replace("__DATA__", json.dumps(d).replace("</", "<\\/"))
            .replace("__STRINGS__", json.dumps(R["js"], ensure_ascii=False).replace("</", "<\\/")))
    open(a.out, "w").write(page)
    print("wrote", a.out, len(page), "bytes")


if __name__ == "__main__":
    main()
