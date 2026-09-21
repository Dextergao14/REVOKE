# Task prompt — REVOKE closed-model evaluation

Paste everything below the line into a coding agent (Claude Code, Codex, Cursor) in an
empty directory. It is self-contained.

---

You are running the closed-model evaluation for the REVOKE benchmark. Work carefully and
report progress **in Chinese (中文)**; everything else — code, commits, file contents — stays
in English.

## What REVOKE measures

An agent reads one very long record (300k–900k tokens: a ward-round log, a release-channel
chat export, a design-review log, a care-circle group chat, a game-narrative review, a
company minute book). Rules arrive, get amended, get overridden, get withdrawn. Ten to
fifteen times per episode the agent is asked to carry out a task by calling one tool with one
of the offered options. An action that contradicts the rules **as they currently stand** is a
violation; an action on an option nobody with authority ever approved does not count as
completing the task. Grading is a boolean query over a recomputed logical closure — no LLM
judge, no human annotation.

Your job is the closed-model half of the evaluation grid. Someone else is running the
open-weight models; do not run those.

## Setup

```bash
git clone https://github.com/Dextergao14/REVOKE.git && cd REVOKE
gh release download v0.5-long100 --dir data/long100    # 125 MB, or download from the Releases page
python3 scripts/long100_summary.py data/long100/manifest.jsonl   # sanity check: 100 episodes
```

Python 3.10+. Read `docs/COLLABORATORS.md` first — it explains the runners and the file
layout. Install the per-system extras before stage B:

```bash
pip install -r eval/memory/requirements-mem0.txt -r eval/memory/requirements-memos.txt \
            -r eval/memory/requirements-memp.txt -r eval/memory/requirements-dynamic_cheatsheet.txt
pip install sentence-transformers      # optional; local embeddings for the retrieval-based systems
```

The API key will be sent to you separately. Put it where it cannot be committed:

```bash
mkdir -p ~/.config/revoke && printf 'OPENROUTER_API_KEY=sk-or-...\n' > ~/.config/revoke/or.env
chmod 600 ~/.config/revoke/or.env
set -a; . ~/.config/revoke/or.env; set +a
```

Everything runs through OpenRouter, so one key covers all three models. Anthropic models need
the account's provider settings to allow their hosts (OpenRouter → Settings → Privacy /
Providers); if `anthropic/claude-opus-5` returns HTTP 404 "No allowed providers", that setting
is the cause — report it and continue with the other two.

## The one rule you must not break

Each episode exists as two files. `*_blind.jsonl.gz` is what a model under test may see.
`*_full.jsonl.gz` carries the ground truth. **Never point a runner, a script or a model at a
`full` file, and never read one yourself to decide anything about a run.** The runners refuse
filenames containing `full` and datasets whose probes carry labels; do not work around that.
Grading reads the full file — that is the only place it belongs.

## Stage A — three closed models at full context (the ceiling)

Every task is answered with the whole transcript so far in the prompt. This is a **ceiling,
not a baseline**: it says what a backbone does when memory is not the problem. No deployment
resends 900k tokens per task, so this row exists to interpret the memory results, not to
compete with them.

```bash
mkdir -p runs/long100/full_closed
python3 eval/adapters/openrouter_runner.py \
    --blind data/long100/long100_blind.jsonl.gz \
    --models openai/gpt-5.5,anthropic/claude-opus-5,meta/muse-spark-1.3-contributor \
    --workers 4 --out runs/long100/full_closed
```

**Before the full run, smoke-test on the two cheapest episodes** (about $5, ten minutes) and
report what you see:

```bash
python3 eval/adapters/openrouter_runner.py --blind data/long100/long100_blind.jsonl.gz \
    --models openai/gpt-5.5,anthropic/claude-opus-5,meta/muse-spark-1.3-contributor \
    --items $(head -2 data/long100/subsample30.txt | tr '\n' ',' | sed 's/,$//') \
    --workers 3 --out runs/long100/smoke
python3 scripts/long_report.py --full data/long100/long100_full.jsonl.gz --runs runs/long100/smoke --detail
```

The runner checkpoints every task to `*.jsonl.part`, so an interrupted run resumes by
re-issuing the same command. Expected cost for the full stage A: about **$2,050 for gpt-5.5,
$2,050 for claude-opus-5, $40 for muse** — the two frontier models dominate the bill because
every task resends up to 900k tokens. Watch for HTTP 402 (OpenRouter reserves credit for
in-flight requests): if a single task fails that way, re-run that one episode alone rather
than the whole model.

Then rank them:

```bash
python3 scripts/pick_best.py --full data/long100/long100_full.jsonl.gz --runs runs/long100/full_closed
```

The last line is the winning model id. **Stop here and report the table before starting
stage B.**

## Stage B — memory systems on the winning model

This is the main table.

One agent runs each episode continuously with a raw window of the last 8,000 tokens; every
session that scrolls out goes to a memory system, which decides what to put back in the prompt
at each task.

```bash
scripts/run_eval_matrix.sh stage2 <WINNER_MODEL_ID>                              # all 100 episodes
scripts/run_eval_matrix.sh stage2 <WINNER_MODEL_ID> data/long100/subsample30.txt # 30-episode subsample
```

Eight conditions run: `full`, `compact`, `compact2k`, `none` as controls and `mem0`, `memos`,
`memp`, `dynamic_cheatsheet` as the systems under test. Memory persists across the episodes of
one world (`--persist`), which is what the "more experience, more violations" claim needs.

**Which of the two depends on the budget you are given — ask before starting.** All 100
episodes on gpt-5.5 or claude-opus-5 costs about **$9,200**; the stratified 30-episode
subsample (one episode per world per length band) costs about **$3,000** and still gives 30
independent clusters. If the winner is muse, run all 100 — it costs about $180.

Verify the cost yourself before committing to it:

```bash
python3 scripts/cost_estimate.py --blind data/long100/long100_blind.jsonl.gz --price 5:30
```

## Reporting

```bash
python3 scripts/long_report.py --full data/long100/long100_full.jsonl.gz \
    --runs runs/long100/full_closed runs/long100/mem --detail
```

Report, in Chinese:

1. **Per model and per condition**: violation rate, completion, abstention, exam score
   (weighted +1 / 0 / −1, negative means worse than never acting), far-span and trap violation
   rates, and cost. Always report violation **and** exam together — a memory condition can
   lower the violation rate purely by refusing to act, and only the exam score shows that.
2. **Every violation you were asked to look at**: `--detail` prints the probe, its recall span
   and what was chosen versus what was licensed.
3. **Anything that smells like a harness artefact rather than a model failure.** The known
   ones: a refusal written into the tool's argument slot (graded as an abstention, never as a
   violation — check the count), HTTP 400 context-window errors on the longest episodes, HTTP
   402 credit reservations, and a memory system whose own LLM call returned empty (each
   adapter counts these in `stats()` — report the counters).
4. **Running cost after each stage**, from the `$` column, against the estimate above.

Do not fix anything in the benchmark itself without asking. If a number looks wrong, say so
with the evidence and stop — a silently "fixed" grader invalidates the whole run.

Report progress in Chinese after: the smoke test, each model finishing stage A, the ranking,
and each condition finishing stage B.
