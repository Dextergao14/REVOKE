// REVOKE — paper progress deck (English).  pptxgenjs, LAYOUT_WIDE 13.33 x 7.5 in.
const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Wentao Gao";
pres.title = "REVOKE — paper progress";

// ---- palette: the paper's own identity.  ink for dark slides, white content,
// indigo accent used sparingly, amber = pending / placeholder, green = measured.
const INK = "14181C", INK2 = "4A535B", MUTED = "7D868E", RULE = "D9DEDF", PAPER = "F4F5F3",
      WHITE = "FFFFFF", INDIGO = "2F3AA6", INDIGO_L = "E6E8F6", AMBER = "D9A800", AMBER_L = "FFF1CC",
      GREEN = "1D6B3A", GREEN_L = "E6F3EA", RED = "B3261E", RED_L = "FBE4E4";
const HEAD = "Cambria", BODY = "Calibri";

const W = 13.333, H = 7.5, M = 0.6;

function title(slide, text, sub) {
  slide.addText(text, { x: M, y: 0.42, w: W - 2 * M, h: 0.75, fontFace: HEAD, fontSize: 30, bold: true,
    color: INK, isTextBox: true, margin: 0, valign: "top" });
  if (sub) slide.addText(sub, { x: M, y: 1.12, w: W - 2 * M, h: 0.4, fontFace: BODY, fontSize: 14,
    color: INK2, isTextBox: true, margin: 0, italic: true });
}
function footer(slide, n) {
  slide.addText(`REVOKE · paper progress · 13 Sep 2026`, { x: M, y: H - 0.45, w: 6, h: 0.3, fontFace: BODY,
    fontSize: 9, color: MUTED, isTextBox: true, margin: 0 });
  slide.addText(String(n), { x: W - M - 0.6, y: H - 0.45, w: 0.6, h: 0.3, fontFace: BODY, fontSize: 9,
    color: MUTED, align: "right", isTextBox: true, margin: 0 });
}
function tag(slide, x, y, text, fg, bg) {
  slide.addText(text, { x, y, w: 0.95, h: 0.26, fontFace: BODY, fontSize: 9, bold: true, color: fg,
    fill: { color: bg }, align: "center", valign: "middle", isTextBox: true, margin: 0, charSpacing: 1 });
}
function card(slide, x, y, w, h, head, body, opts = {}) {
  slide.addShape(pres.ShapeType.rect, { x, y, w, h, fill: { color: opts.fill || PAPER }, line: { color: opts.line || RULE, width: 0.75 } });
  slide.addText(head, { x: x + 0.22, y: y + 0.16, w: w - 0.44, h: 0.38, fontFace: HEAD, fontSize: opts.headSize || 15, bold: true,
    color: opts.headColor || INK, isTextBox: true, margin: 0, valign: "top" });
  slide.addText(body, { x: x + 0.22, y: y + 0.58, w: w - 0.44, h: h - 0.72, fontFace: BODY, fontSize: opts.bodySize || 12.5,
    color: INK2, isTextBox: true, margin: 0, valign: "top", paraSpaceAfter: 4 });
}
function bullets(slide, x, y, w, h, items, size = 14) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < items.length - 1 } })),
    { x, y, w, h, fontFace: BODY, fontSize: size, color: INK, isTextBox: true, margin: 0, valign: "top", paraSpaceAfter: 6 });
}
function stat(slide, x, y, w, big, label, color = INK) {
  slide.addText(big, { x, y, w, h: 0.9, fontFace: HEAD, fontSize: 40, bold: true, color, isTextBox: true, margin: 0, valign: "bottom" });
  slide.addText(label, { x, y: y + 0.92, w, h: 0.5, fontFace: BODY, fontSize: 12, color: INK2, isTextBox: true, margin: 0, valign: "top" });
}
const th = (t, align) => ({ text: t, options: { bold: true, color: INK, fill: { color: WHITE }, align: align || "left", border: [{ type: "none" }, { type: "none" }, { pt: 1, color: INK }, { type: "none" }] } });
const td = (t, opts = {}) => ({ text: t, options: Object.assign({ color: INK2, align: "left", border: [{ type: "none" }, { type: "none" }, { pt: 0.5, color: RULE }, { type: "none" }] }, opts) });
const tdr = (t, opts = {}) => td(t, Object.assign({ align: "right" }, opts));
const tdn = (t, opts = {}) => tdr(t, Object.assign({ color: INK }, opts));
const tdneg = (t) => tdr(t, { color: "8A5A00" });
const stackChart = (slide, x, y, w, h, labels, viol, done, abst, titleText) => {
  // drawn with shapes so every renderer shows the same thing
  slide.addText(titleText, { x, y, w, h: 0.35, fontFace: HEAD, fontSize: 12.5, bold: true, color: INK, isTextBox: true, margin: 0 });
  const labW = 2.35, barX = x + labW + 0.15, barW = w - labW - 0.15, top = y + 0.5, avail = h - 0.5 - 0.5;
  const rowH = Math.min(0.62, avail / labels.length), barH = rowH * 0.62;
  labels.forEach((lab, i) => {
    const ry = top + i * rowH;
    slide.addText(lab, { x, y: ry, w: labW, h: barH, fontFace: BODY, fontSize: 11, color: INK, isTextBox: true, margin: 0, valign: "middle", align: "right" });
    let cx = barX;
    [[viol[i], RED], [done[i], GREEN], [abst[i], "B9BEC4"]].forEach(([v, col]) => {
      if (v <= 0) return;
      const sw = barW * v;
      slide.addShape(pres.ShapeType.rect, { x: cx, y: ry, w: sw, h: barH, fill: { color: col }, line: { color: WHITE, width: 0.75 } });
      if (sw > 0.42) slide.addText(v.toFixed(2), { x: cx, y: ry, w: sw, h: barH, fontFace: BODY, fontSize: 9.5, bold: true, color: WHITE, align: "center", valign: "middle", isTextBox: true, margin: 0 });
      cx += sw;
    });
  });
  const ly = top + labels.length * rowH + 0.12;
  [["Violation", RED], ["Completion", GREEN], ["Abstention", "B9BEC4"]].forEach(([t, col], i) => {
    const lx = barX + i * 1.55;
    slide.addShape(pres.ShapeType.rect, { x: lx, y: ly + 0.05, w: 0.16, h: 0.16, fill: { color: col }, line: { color: col } });
    slide.addText(t, { x: lx + 0.22, y: ly, w: 1.25, h: 0.26, fontFace: BODY, fontSize: 10, color: INK2, isTextBox: true, margin: 0, valign: "middle" });
  });
};

// =============================================================== 1 title (dark)
{
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText("REVOKE", { x: M, y: 1.35, w: 6, h: 0.5, fontFace: BODY, fontSize: 14, color: "A4AAF3", bold: true, charSpacing: 6, isTextBox: true, margin: 0 });
  s.addText("Does an Agent's Experience Expire When the Rules Do?", { x: M, y: 1.9, w: W - 2 * M - 1, h: 1.9, fontFace: HEAD, fontSize: 40, bold: true, color: WHITE, isTextBox: true, margin: 0, valign: "top" });
  s.addText("A behavioural benchmark for procedural memory invalidation under rule evolution", { x: M, y: 3.85, w: 9.5, h: 0.6, fontFace: BODY, fontSize: 18, italic: true, color: "CFD3D8", isTextBox: true, margin: 0 });
  s.addText("Paper progress · 13 September 2026", { x: M, y: 5.2, w: 6, h: 0.4, fontFace: BODY, fontSize: 14, color: "CFD3D8", isTextBox: true, margin: 0 });
  s.addText("Wentao Gao · The University of Texas at Arlington", { x: M, y: 5.6, w: 8, h: 0.4, fontFace: BODY, fontSize: 14, color: "CFD3D8", isTextBox: true, margin: 0 });
  // status chips
  const chips = [["measured", GREEN, GREEN_L], ["pending", "8A5A00", AMBER_L]];
  chips.forEach((c, i) => tag(s, M + i * 1.1, 6.35, c[0], c[1], c[2]));
  s.addText("Colour key used throughout: green = measured on our own runs; amber = placeholder pending the full evaluation.", { x: M + 2.3, y: 6.33, w: 9, h: 0.3, fontFace: BODY, fontSize: 10, color: "9AA0A8", isTextBox: true, margin: 0 });
  s.addNotes("Progress deck for the REVOKE benchmark paper. Everything green was measured on our own runs this month; amber items are still to be filled by the full evaluation.");
}

// =============================================================== 2 the question
{
  const s = pres.addSlide();
  title(s, "The question no memory benchmark asks", "When the rules of the world change, does what memory holds remain valid — and does behaviour show it?");
  card(s, M, 1.75, 5.9, 2.35, "Declarative memory middleware", "mem0, MemOS, Zep, OmniMemory. Evaluated by long-horizon QA (LoCoMo, LongMemEval): did the system remember correctly? StateMemBench adds revised state, but still grades answers, not actions.", { headColor: INDIGO });
  card(s, M + 6.15, 1.75, 5.9, 2.35, "Self-evolving experiential memory", "ExpeL, Agent Workflow Memory, Voyager, SkillWeaver, Dynamic Cheatsheet, MemEvolve. Evaluated by task success on GAIA / WebArena: did the agent get better at doing? Never tested against a world whose rules move.", { headColor: INDIGO });
  s.addShape(pres.ShapeType.rect, { x: M, y: 4.4, w: W - 2 * M, h: 2.2, fill: { color: INK }, line: { color: INK } });
  s.addText("Procedural memory invalidation", { x: M + 0.3, y: 4.58, w: 6, h: 0.45, fontFace: HEAD, fontSize: 20, bold: true, color: WHITE, isTextBox: true, margin: 0 });
  s.addText("Every distilled insight and consolidated workflow was validated under some particular world state. When constraints evolve, that experience does not expire on its own: it keeps being retrieved, and because it still works on the old distribution it survives success-driven selection. The counterintuitive pattern: more experience, more violations.", { x: M + 0.3, y: 5.05, w: W - 2 * M - 0.6, h: 1.4, fontFace: BODY, fontSize: 14, color: "E4E7EA", isTextBox: true, margin: 0, valign: "top" });
  footer(s, 2);
}

// =============================================================== 3 two-layer construction
{
  const s = pres.addSlide();
  title(s, "Ground truth is computed, not annotated", "Two layers: a persistent base of defeasible rules with priorities, and a derivation layer recomputed at every session");
  const steps = [["1  Ground", "R_t → N_t", "Instantiate every live rule over the sorted universe. Nodes are ground instances, so a rule defeated in one context stays valid in another."],
                 ["2  Defeat graph", "n → m", "An edge whenever two instances have complementary heads and π(n) > π(m). Strict priorities: acyclic."],
                 ["3  Grounded extension", "E_t, D_t", "Iterated deletion to fixpoint (Dung 1995): unique, polynomial, deletion-order independent."],
                 ["4  Closure", "C_t", "Stratified forward chaining over survivors only, recomputed from scratch — no Delete-and-Rederive."]];
  const bw = (W - 2 * M - 3 * 0.25) / 4;
  steps.forEach((st, i) => {
    const x = M + i * (bw + 0.25);
    s.addShape(pres.ShapeType.rect, { x, y: 1.8, w: bw, h: 2.15, fill: { color: PAPER }, line: { color: RULE, width: 0.75 } });
    s.addText(st[0], { x: x + 0.2, y: 1.95, w: bw - 0.4, h: 0.4, fontFace: HEAD, fontSize: 15, bold: true, color: INK, isTextBox: true, margin: 0 });
    s.addText(st[1], { x: x + 0.2, y: 2.35, w: bw - 0.4, h: 0.3, fontFace: "Courier New", fontSize: 11, color: INDIGO, isTextBox: true, margin: 0 });
    s.addText(st[2], { x: x + 0.2, y: 2.7, w: bw - 0.4, h: 1.55, fontFace: BODY, fontSize: 11.5, color: INK2, isTextBox: true, margin: 0, valign: "top" });
    if (i < 3) s.addText("›", { x: x + bw - 0.02, y: 2.75, w: 0.3, h: 0.5, fontFace: HEAD, fontSize: 28, color: MUTED, isTextBox: true, margin: 0, align: "center" });
  });
  s.addText([{ text: "Violation ", options: { bold: true, color: INK } }, { text: "iff  C_t ∪ assert(a) derives a contradiction. Six events drive evolution: ", options: { color: INK2 } },
             { text: "Add · Supersede · Condition · Conflict · Support · Retract", options: { color: INDIGO, bold: true } },
             { text: ". Support changes no rule text — it raises a priority, and a single increment can flip the whole extension. Permissive default: a silent closure is not a violation.", options: { color: INK2 } }],
    { x: M, y: 4.25, w: W - 2 * M, h: 1.0, fontFace: BODY, fontSize: 14, isTextBox: true, margin: 0, valign: "top" });
  s.addShape(pres.ShapeType.rect, { x: M, y: 5.45, w: W - 2 * M, h: 0.85, fill: { color: GREEN_L }, line: { color: GREEN_L } });
  s.addText("No LLM judge anywhere. Grading is a boolean query over a recomputed closure; both worked examples of the design note run as executable tests of the engine.", { x: M + 0.25, y: 5.55, w: W - 2 * M - 0.5, h: 0.65, fontFace: BODY, fontSize: 13.5, color: GREEN, isTextBox: true, margin: 0, valign: "middle" });
  footer(s, 3);
}

// =============================================================== 4 generator
{
  const s = pres.addSlide();
  title(s, "The generator is a graph traversal", "Reusable event-subgraph motifs → randomised topological linearisation → ground truth re-scored by the solver");
  bullets(s, M, 1.75, 5.6, 4.6, [
    "A motif is a small, domain-agnostic event subgraph over allow/1, context predicates and grp/2; it emits an ordered chain of beats, each optionally followed by a probe (a task).",
    "Chains are mutually independent, so all beats form a DAG; the generator draws a weighted random linear extension and lays it on a session grid with filler, distractors and echo probes.",
    "Ground truth is never the motif's intent: every probe is re-scored against the closure the solver actually produces at that session.",
    "Seven acceptance checks; failures are rejected, never repaired: consistency at every session, no must-violate probe, over-deletion guard, a stale-memory trap, rendered probes, self-containedness, priority recoverability.",
  ], 13.5);
  const rows = [[th("Motif"), th("What a stale memory gets wrong")],
    [td("conflict_flip / support_threshold"), td("a priority increment re-permits a banned entity; no text changes")],
    [td("conditionalize / condition_widen"), td("a blanket ban narrows, then the qualifier disappears")],
    [td("retract_partial / group_dynamics"), td("membership stated dozens of sessions earlier")],
    [td("hierarchy / stale_reminder"), td("recency is not authority; reminders are not rules")],
    [td("alias / derived / conjunctive"), td("transitive, never-stated, or two-condition prohibitions")],
    [td("threshold"), td("a numeric limit that moves; the task carries a value")],
    [td("certification regime"), td("off-list use is a violation while the flag is on")]];
  s.addTable(rows, { x: M + 5.95, y: 1.75, w: W - 2 * M - 5.95, colW: [2.55, 3.58], fontFace: BODY, fontSize: 11, rowH: 0.42, valign: "middle", margin: 0.06 });
  footer(s, 4);
}

// =============================================================== 5 tiers and worlds
{
  const s = pres.addSlide();
  title(s, "Three tiers, six worlds", "Same engine and grader everywhere; the world contributes vocabulary, people and prose");
  card(s, M, 1.75, 3.9, 2.0, "Easy tier", "10–40 sessions, one team voice, obviously irrelevant filler. Saturated: a $0.02/M open model reaches CSR 0.98 with zero violations. Kept as the easy split.", { bodySize: 12 });
  card(s, M + 4.12, 1.75, 3.9, 2.0, "Hard tier", "60–140 sessions, declared speaker hierarchy (rank beats recency), near-miss noise from people with no authority, nudged requesters, terse referential updates.", { bodySize: 12 });
  card(s, M + 8.24, 1.75, 3.9, 2.0, "Long tier", "420–670 sessions rendered as a realistic record of 300k–1M tokens; 10–15 released tasks per episode drawn from a pool of 180–270.", { bodySize: 12, fill: INDIGO_L, line: INDIGO_L, headColor: INDIGO });
  const worlds = [["Ward round & nursing handover", "sectioned", "administer one drug"], ["#platform-release chat export", "flat", "call one endpoint"],
                  ["Design crit notes + design-system log", "sectioned", "place one component"], ["Care-circle group chat", "flat", "suggest one activity"],
                  ["Live-service game narrative review", "sectioned", "deploy one story beat"], ["Company minute book (AI notetaker)", "sectioned", "run work through one tool"]];
  const rows = [[th("World"), th("Layout"), th("The graded act")]].concat(worlds.map(w => [td(w[0], { color: INK }), td(w[1]), td(w[2])]));
  s.addTable(rows, { x: M, y: 4.05, w: W - 2 * M, colW: [5.2, 2.2, 4.73], fontFace: BODY, fontSize: 12, rowH: 0.36, valign: "middle", margin: 0.05 });
  footer(s, 5);
}

// =============================================================== 6 long tier construction
{
  const s = pres.addSlide();
  title(s, "The long tier: a rule history laid onto a real document", "A world is a JSON corpus of vocabulary and surface; the engine, events and grader are untouched");
  card(s, M, 1.75, 5.9, 1.55, "Two layouts", "Sectioned: rules under a Decisions heading, chatter under Discussion (including decision-phrased lines from people with no authority), the task under Action Items. Flat: one stream with a speaker on every line and nothing marking what is a rule.", { bodySize: 12 });
  card(s, M + 6.15, 1.75, 5.9, 1.55, "Filler that cannot change the closure", "Slot templates with a product of ~10⁹ lines: filler never names a governed entity and never uses the rule register. Both invariants are enforced by a validator and again by the padder. Duplication in the release build: 1.1–2.1%.", { bodySize: 12 });
  card(s, M, 3.5, 5.9, 1.55, "Rank neutrality", "The engine decides who speaks a rule template — often a rank-1 person — so no template may claim an authority the grader will not grant its speaker. The first corpora had 69 such lines; the validator now rejects them.", { bodySize: 12 });
  card(s, M + 6.15, 3.5, 5.9, 1.55, "Anchors with arcs", "The always-approved anchors that keep every task completable now carry rank-3 ban/reinstate arcs, and the selector avoids tasks answerable by \"approved early, never restricted\": 48/50 pilot tasks were of that kind; 19/1202 released tasks are.", { bodySize: 12 });
  s.addShape(pres.ShapeType.rect, { x: M, y: 5.3, w: W - 2 * M, h: 1.25, fill: { color: PAPER }, line: { color: RULE, width: 0.75 } });
  s.addText([{ text: "Task pool.  ", options: { bold: true, color: INK } }, { text: "Every episode ships its full pool of generated tasks (session, options, labels, difficulty, rendered task text). The released 10–15 are one selection; ", options: { color: INK2 } }, { text: "scripts/reselect_probes.py", options: { fontFace: "Courier New", color: INDIGO } }, { text: " builds another from the same history, graded by the same code.", options: { color: INK2 } }],
    { x: M + 0.25, y: 5.42, w: W - 2 * M - 0.5, h: 1.0, fontFace: BODY, fontSize: 13, isTextBox: true, margin: 0, valign: "middle" });
  footer(s, 6);
}

// =============================================================== 7 dataset status
{
  const s = pres.addSlide();
  title(s, "Dataset status", "The long-tier release was built on 12 September: one run, eight processes, no failed seed");
  stat(s, M, 1.7, 2.6, "100", "long-tier episodes", GREEN);
  stat(s, M + 2.75, 1.7, 2.6, "1,202", "released tasks", GREEN);
  stat(s, M + 5.5, 1.7, 2.9, "21,996", "tasks in the pools", GREEN);
  stat(s, M + 8.6, 1.7, 3.2, "62.7M", "tokens in total", GREEN);
  const rows = [[th("Band (target)"), th("Episodes", "right"), th("Rendered length", "right"), th("Sessions", "right"), th("Tasks / ep.", "right"), th("Released tasks", "right"), th("Stale traps", "right"), th("Recall span > 200", "right")],
    [td("300k"), tdn("24"), tdn("344k–371k"), tdn("445"), tdn("10"), tdn("240"), tdn("0.72"), tdn("0.79")],
    [td("440k"), tdn("22"), tdn("490k–520k"), tdn("499"), tdn("11"), tdn("242"), tdn("0.74"), tdn("0.81")],
    [td("580k"), tdn("18"), tdn("637k–671k"), tdn("551"), tdn("12"), tdn("216"), tdn("0.70"), tdn("0.83")],
    [td("720k"), tdn("18"), tdn("785k–821k"), tdn("606"), tdn("13"), tdn("234"), tdn("0.70"), tdn("0.77")],
    [td("830k"), tdn("18"), tdn("897k–934k"), tdn("649"), tdn("15"), tdn("270"), tdn("0.67"), tdn("0.83")]];
  s.addTable(rows, { x: M, y: 3.35, w: W - 2 * M, colW: [1.6, 1.2, 1.9, 1.3, 1.4, 1.7, 1.5, 1.53], fontFace: BODY, fontSize: 12, rowH: 0.38, valign: "middle", margin: 0.05 });
  s.addText("Also released: 1,000 easy-tier episodes (17,702 graded decisions). Hard tier and the five-episode long-tier pilot (v1, v2) are kept as pilots. Real prompt tokens at the API are within 3% of the estimate; the top band stays under every 1M window.", { x: M, y: 5.9, w: W - 2 * M, h: 0.7, fontFace: BODY, fontSize: 12, color: INK2, isTextBox: true, margin: 0, valign: "top" });
  footer(s, 7);
}

// =============================================================== 8 protocol and metrics
{
  const s = pres.addSlide();
  title(s, "Protocol and metrics", "Only the blind view reaches an agent; the grader rebuilds ground truth from the event log and never trusts cached labels");
  card(s, M, 1.75, 3.9, 3.2, "Memory conditions", "full — whole transcript in context (upper bound).\n\ncompact-K — one agent runs the episode continuously; as the K-token budget overflows, the oldest sessions are rewritten into bounded running notes (≤ K/2) it must later act on.\n\ntruncate — drop without notes (ablation only). Middleware and experiential systems: planned.", { bodySize: 12 });
  card(s, M + 4.12, 1.75, 3.9, 3.2, "Three outcomes per task", "done — acted on an option the closure positively licenses (allow(e) ∈ C_t).\n\nviolated — the action contradicts the closure.\n\nabstained — neither. Violation alone hides paralysis: a compacting agent that refuses 58% of tasks looks clean.", { bodySize: 12 });
  card(s, M + 8.24, 1.75, 3.9, 3.2, "Exam score and weight", "Task score +1 / 0 / −1, weighted and averaged into [−1, 1]; negative = worse than never acting.\n\nw = 1 + 1.0·[span > 200] + 0.8·[trap] + 0.4·(n_viol − 1)⁺ − 0.3·(n_lic − 1)⁺, floor 0.3 — from ground truth alone. Position is deliberately not a feature.", { bodySize: 12 });
  s.addShape(pres.ShapeType.rect, { x: M, y: 5.2, w: W - 2 * M, h: 1.35, fill: { color: PAPER }, line: { color: RULE, width: 0.75 } });
  s.addText([{ text: "Reading the action.  ", options: { bold: true, color: INK } }, { text: "The act tool's argument must name one entity: an exact name, or a short single-line phrase naming exactly one (leading article ignored). A paragraph that enumerates the options before declining is a refusal → abstention. This rule was forced by the pilot: substring matching had scored 53% of one condition's refusals as violations.", options: { color: INK2 } }],
    { x: M + 0.25, y: 5.3, w: W - 2 * M - 0.5, h: 1.15, fontFace: BODY, fontSize: 13, isTextBox: true, margin: 0, valign: "middle" });
  footer(s, 8);
}

// =============================================================== 9 scripted policies
{
  const s = pres.addSlide();
  title(s, "Scripted reference policies on all 1,202 released tasks", "No model calls; the floor, the ceiling, and proof that the benchmark separates the behaviours it claims to");
  tag(s, W - M - 0.95, 0.5, "measured", GREEN, GREEN_L);
  stackChart(s, M, 1.7, 7.2, 4.9, ["oracle", "stale", "recency", "random", "refuse"], [0, 0.79, 0.84, 0.63, 0], [1, 0.21, 0.16, 0.23, 0], [0, 0, 0, 0.14, 1], "Outcome of every task, by policy");
  const rows = [[th("Policy"), th("Exam", "right"), th("Trap viol.", "right")],
    [td("oracle — always a licensed option", { color: INK }), tdn("+1.00"), tdn("0.00")],
    [td("stale — replay last compliant choice", { color: INK }), tdneg("−0.63"), tdn("0.96")],
    [td("recency — most recently named", { color: INK }), tdneg("−0.69"), tdn("0.84")],
    [td("random — uniform over options", { color: INK }), tdneg("−0.44"), tdn("0.62")],
    [td("refuse — never act", { color: INK }), tdn("0.00"), tdn("0.00")]];
  s.addTable(rows, { x: M + 7.5, y: 1.85, w: W - 2 * M - 7.5, colW: [2.75, 0.9, 0.98], fontFace: BODY, fontSize: 11.5, rowH: 0.42, valign: "middle", margin: 0.05 });
  s.addText("Option sets are tight — on average one licensed option among five — so random violates two tasks in three. The stale policy's trap violation of 0.96 is the number the benchmark exists to produce.", { x: M + 7.5, y: 4.55, w: W - 2 * M - 7.5, h: 1.6, fontFace: BODY, fontSize: 12, color: INK2, isTextBox: true, margin: 0, valign: "top" });
  footer(s, 9);
}

// =============================================================== 10 pilot: full context
{
  const s = pres.addSlide();
  title(s, "Pilot: the whole record in context, no memory system", "Five episodes (368k–1018k), one seed, 50 tasks; every violation checked against the events that cause it");
  tag(s, W - M - 0.95, 0.5, "measured", GREEN, GREEN_L);
  stackChart(s, M, 1.65, 6.6, 4.95, ["gpt-5.5 (20 tasks)", "deepseek-v4-flash", "glm-5.3-flash", "qwen3.7-flash"], [0.10, 0.34, 0.40, 0.74], [0.90, 0.44, 0.38, 0.19], [0.00, 0.22, 0.22, 0.06], "v2 episodes (released construction)");
  const rows = [[th("Backbone"), th("Viol.", "right"), th("Exam", "right")],
    [td("gpt-5.5 · frontier", { color: INK }), tdn("0.10"), tdn("+0.81")],
    [td("deepseek-v4-pro · pro (v1)", { color: INK }), tdn("0.17"), tdn("+0.41")],
    [td("glm-5.3 · pro (v1)", { color: INK }), tdn("0.21"), tdn("+0.38")],
    [td("deepseek-v4-flash", { color: INK }), tdn("0.34"), tdn("+0.07")],
    [td("glm-5.3-flash", { color: INK }), tdn("0.40"), tdneg("−0.04")],
    [td("qwen3.7-flash", { color: INK }), tdn("0.74"), tdneg("−0.57")]];
  s.addTable(rows, { x: M + 6.9, y: 1.8, w: W - 2 * M - 6.9, colW: [3.03, 1.0, 1.2], fontFace: BODY, fontSize: 11.5, rowH: 0.4, valign: "middle", margin: 0.05 });
  s.addText("Three tiers of backbone, one ordering, on both builds and across worlds. glm-5.3-flash's −0.04 exam score says that with the entire transcript available it did slightly worse than an agent that never acts. Cost: fifty million-token tasks grade for $1–3 on the flash tier; $12 per 20 tasks for gpt-5.5.", { x: M + 6.9, y: 4.75, w: W - 2 * M - 6.9, h: 1.7, fontFace: BODY, fontSize: 12, color: INK2, isTextBox: true, margin: 0, valign: "top" });
  footer(s, 10);
}

// =============================================================== 11 what goes wrong
{
  const s = pres.addSlide();
  title(s, "What goes wrong", "Three findings from reading every violation — one of them about our own construction");
  tag(s, W - M - 0.95, 0.5, "measured", GREEN, GREEN_L);
  card(s, M, 1.75, 3.9, 4.8, "A rule with an on/off state", "The certification regime — a rank-3 rule stated in session 6–8: while a flag is on, only listed options may be used; the flag toggles every few dozen sessions and the list is amended.\n\nIt is behind 16 of glm's 20 violations, 16 of deepseek's 17, 30 of qwen's 35, and 1 of gpt-5.5's 2. Models read the rule, watch the list change, then act as if the flag were off.\n\nA rank-0 nudge (\"refunds-async should be fine, no?\") was followed into a violation on 10 of 28 nudged tasks.", { bodySize: 12 });
  card(s, M + 4.12, 1.75, 3.9, 4.8, "Structure, not length", "The 1018k narrative review is not the hardest episode for any model; for glm-5.3-flash it is the easiest (violation 0.30, exam +0.41).\n\nThe two flat chat exports and the design log are the hardest: a rule that arrives as one line among a hundred, from a speaker whose rank has to be looked up, with nothing marking it as a decision.\n\nDifficulty comes from the record's structure and the state's history.", { bodySize: 12 });
  card(s, M + 8.24, 1.75, 3.9, 4.8, "The anchor lesson", "In the first build, 48 of 50 tasks had as their only licensed option an entity approved in session 2–4 and never restricted since. gpt-5.5 found those by absence: 30/30 correct, without tracking anything.\n\nAnchors now carry ban/reinstate arcs and the selector avoids never-restricted tasks: 1/50 pilot, 19/1202 release.\n\nFlash tier unaffected (0.36–0.66 → 0.34–0.74); the frontier model went from 0 to 2 violations in 20, both 350+ sessions after the rule they broke.", { bodySize: 12, fill: INDIGO_L, line: INDIGO_L, headColor: INDIGO });
  footer(s, 11);
}

// =============================================================== 12 compaction
{
  const s = pres.addSlide();
  title(s, "Pilot: one agent, the whole episode, a bounded memory", "glm-5.3-flash running each v2 episode continuously; material leaving the context is rewritten into notes it must act on later");
  tag(s, W - M - 0.95, 0.5, "measured", GREEN, GREEN_L);
  stackChart(s, M, 1.65, 6.6, 4.3, ["full context", "compact-2k · keep 55% · notes ≤1.2k", "compact-8k · keep 93% · notes ≤4k"], [0.40, 0.26, 0.28], [0.38, 0.16, 0.40], [0.22, 0.58, 0.32], "50 tasks per condition");
  const rows = [[th("Condition"), th("Exam", "right"), th("Compactions / ep.", "right"), th("Context at task", "right")],
    [td("full context", { color: INK }), tdneg("−0.04"), tdn("0"), tdn("368k–1018k")],
    [td("compact-2k", { color: INK }), tdneg("−0.12"), tdn("417"), tdn("2.1k")],
    [td("compact-8k", { color: INK }), tdn("+0.10"), tdn("399"), tdn("10.2k")]];
  s.addTable(rows, { x: M + 6.9, y: 1.8, w: W - 2 * M - 6.9, colW: [1.7, 0.9, 1.4, 1.23], fontFace: BODY, fontSize: 11.5, rowH: 0.42, valign: "middle", margin: 0.05 });
  s.addText("A maintained memory lowers violation below full context (0.40 → 0.26–0.28), reproducing the shorter tier's finding — but the 2k budget does it by abstaining on 58% of tasks. The 8k budget with ~400 small compactions per episode is the only condition on which this backbone scores above zero.", { x: M + 6.9, y: 3.7, w: W - 2 * M - 6.9, h: 1.55, fontFace: BODY, fontSize: 12, color: INK2, isTextBox: true, margin: 0, valign: "top" });
  s.addShape(pres.ShapeType.rect, { x: M, y: 6.05, w: W - 2 * M, h: 0.55, fill: { color: AMBER_L }, line: { color: AMBER_L } });
  s.addText("Protocol lesson: left to itself the model grew its notes by 2–3k characters per session until the notes alone exceeded the budget. Notes are now capped at half the budget with a condensing pass; the unbounded runs were discarded.", { x: M + 0.25, y: 6.08, w: W - 2 * M - 0.5, h: 0.5, fontFace: BODY, fontSize: 11.5, color: "8A5A00", isTextBox: true, margin: 0, valign: "middle" });
  footer(s, 12);
}

// =============================================================== 13 paper status
{
  const s = pres.addSlide();
  title(s, "Where the paper stands", "Draft v0.4 in HTML and as an ICLR 2027 LaTeX project; the construction and the pilot are written, the main table is not");
  const done = ["Formalisation, worked example, properties", "Generator, motif library, acceptance checks", "Long tier: corpora, layouts, invariants, task pool", "Protocol, three outcomes, exam score, weight", "Scripted policies on 1,202 tasks", "Pilot: 7 backbones, 2 memory conditions, causes", "Limitations, reproducibility statement", "Tooling: viewer, reselection, manifest, release README"];
  const pending = ["Main results table across memory systems", "Middleware and experiential conditions", "Frontier backbones under compaction", "Per-event decomposition, lag, interference, attribution", "Human validation sample (~100 tasks, κ)", "Three bibliography stubs (StateMemBench, MemEvolve, EvolveLab)", "Headline finding in abstract and conclusion"];
  s.addShape(pres.ShapeType.rect, { x: M, y: 1.75, w: 5.9, h: 4.85, fill: { color: GREEN_L }, line: { color: GREEN_L } });
  s.addText("Written and measured", { x: M + 0.25, y: 1.9, w: 5.4, h: 0.4, fontFace: HEAD, fontSize: 16, bold: true, color: GREEN, isTextBox: true, margin: 0 });
  s.addText(done.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < done.length - 1 } })), { x: M + 0.25, y: 2.4, w: 5.4, h: 4.1, fontFace: BODY, fontSize: 13, color: INK, isTextBox: true, margin: 0, valign: "top", paraSpaceAfter: 5 });
  s.addShape(pres.ShapeType.rect, { x: M + 6.15, y: 1.75, w: 5.9, h: 4.85, fill: { color: AMBER_L }, line: { color: AMBER_L } });
  s.addText("Placeholders awaiting the full evaluation", { x: M + 6.4, y: 1.9, w: 5.4, h: 0.4, fontFace: HEAD, fontSize: 16, bold: true, color: "8A5A00", isTextBox: true, margin: 0 });
  s.addText(pending.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < pending.length - 1 } })), { x: M + 6.4, y: 2.4, w: 5.4, h: 4.1, fontFace: BODY, fontSize: 13, color: INK, isTextBox: true, margin: 0, valign: "top", paraSpaceAfter: 5 });
  footer(s, 13);
}

// =============================================================== 14 next steps (dark)
{
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText("Next steps", { x: M, y: 0.5, w: 8, h: 0.7, fontFace: HEAD, fontSize: 30, bold: true, color: WHITE, isTextBox: true, margin: 0 });
  const cols = [["Evaluate the release", "Flash tier, full context, 100 episodes: ≈ $30 for three vendors.\nPro tier: ≈ $25.\ngpt-5.5 on a 20-episode stratified sample: ≈ $60.\nglm compact grid: ≈ $130.\nFrontier under compaction is the open cost question ($30/M output × 400 note-writing calls per episode)."],
                ["Close the reviewer gaps", "Human validation on ~100 tasks with agreement κ.\nMore filler registers and an LLM instantiation pass over the same event graph for surface realism.\nMiddleware and experiential conditions through the plain harness.\nEpisode-level confidence intervals (100 clusters)."],
                ["Write", "Fill the main table and the headline finding.\nThree bibliography entries.\nVenue: ICLR 2027 main track (template ready); NeurIPS Datasets & Benchmarks as the natural alternative."]];
  const cw = (W - 2 * M - 2 * 0.3) / 3;
  cols.forEach((c, i) => {
    const x = M + i * (cw + 0.3);
    s.addShape(pres.ShapeType.rect, { x, y: 1.55, w: cw, h: 4.6, fill: { color: "1F262D" }, line: { color: "2A333B", width: 0.75 } });
    s.addText(c[0], { x: x + 0.25, y: 1.72, w: cw - 0.5, h: 0.45, fontFace: HEAD, fontSize: 17, bold: true, color: "A4AAF3", isTextBox: true, margin: 0 });
    s.addText(c[1], { x: x + 0.25, y: 2.25, w: cw - 0.5, h: 3.75, fontFace: BODY, fontSize: 13, color: "E4E7EA", isTextBox: true, margin: 0, valign: "top", paraSpaceAfter: 6 });
  });
  s.addText("github.com/Dextergao14/REVOKE — engine, generator, corpora, grader, 100-episode manifest, pilot runs, paper source", { x: M, y: 6.5, w: W - 2 * M, h: 0.4, fontFace: BODY, fontSize: 12, color: "9AA0A8", isTextBox: true, margin: 0 });
}

pres.writeFile({ fileName: "REVOKE_paper_progress.pptx" }).then(f => console.log("wrote", f));
