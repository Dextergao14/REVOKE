# REVOKE — quickstart for collaborators running evaluations

## 1. Clone and fetch the data

```bash
git clone https://github.com/Dextergao14/REVOKE.git && cd REVOKE
# the 100-episode long tier (125 MB gzipped) is a GitHub release, not in git:
gh release download v0.5-long100 --dir data/long100      # or download from the Releases page
python3 scripts/long100_summary.py data/long100/manifest.jsonl
```

Python 3.10+, no compiled dependencies for the core. `pip install sentence-transformers`
is optional (local embeddings for memory systems that retrieve; without it a hashed
bag-of-words embedder is used). Individual memory systems list their own extras in
`eval/memory/requirements-<name>.txt`.

## 2. Keys

Only OpenRouter is used, so every model runs through one API. Put the key in a file
that is never committed (`*.env` is gitignored):

```bash
mkdir -p ~/.config/revoke && printf 'OPENROUTER_API_KEY=sk-or-...\n' > ~/.config/revoke/or.env && chmod 600 ~/.config/revoke/or.env
set -a; . ~/.config/revoke/or.env; set +a
```

Anthropic and Google models require the account's provider settings to allow their
hosts (OpenRouter → Settings → Providers / Privacy); otherwise they return 404.

## 3. The two files an episode has

`<id>_blind.jsonl.gz` is what an agent under test may see: transcript, tool surface,
option sets. `<id>_full.jsonl.gz` carries ground truth (events, per-session closures,
labels, the task pool). **Never point a runner at a full file** — the runners refuse
filenames containing `full` and datasets whose probes carry labels.

## 4. Runners

| runner | condition | when to use |
|---|---|---|
| `eval/adapters/openrouter_runner.py` | full context, one fresh call per task | upper bound; needs a model with a window ≥ the episode |
| `eval/adapters/episode_runner.py` | one agent runs the episode continuously; `compact` (bounded notes) / `truncate` | the pilot's memory conditions |
| `eval/adapters/memory_runner.py` | same continuous pass, with a pluggable memory system (`--memory mem0`, `memos`, `dilu`, `generative_agents`, `memp`, `dynamic_cheatsheet`, or built-in `compact` / `none` / `full`) | the paper's main table |

Examples:

```bash
# full context, three flash models, all 100 episodes (~$10 per model)
python3 eval/adapters/openrouter_runner.py --blind data/long100/long100_blind.jsonl.gz \
    --models z-ai/glm-5.3-flash,deepseek/deepseek-v4-flash,qwen/qwen3.7-flash --workers 5 --out runs/long100/full

# a memory system on one backbone, 8k raw window, cross-episode consolidation within each world
python3 eval/adapters/memory_runner.py --blind data/long100/long100_blind.jsonl.gz \
    --model z-ai/glm-5.3-flash --memory dilu --window 8000 --persist --workers 4 --out runs/long100/mem

# grade anything
python3 scripts/long_report.py --full data/long100/long100_full.jsonl.gz --runs runs/long100/full runs/long100/mem --detail
```

Every runner checkpoints per task (`*.jsonl.part`) and can be re-run to fill gaps.
Before trusting a run, check the contamination note in `scripts/long_report.py --detail`:
a refusal written into the act tool's argument is scored as an abstention, never as a
violation.

## 5. Adding a memory system

Implement `eval/memory/<name>.py` with a `Backend(MemoryBackend)` class (see
`eval/memory/base.py` for the six-call contract) and make
`python3 scripts/smoke_memory.py --memory <name>` print OK. The memory system's own
LLM calls must go through the shared `self.llm` so it runs on the backbone under test
and its tokens are counted; it must never receive a correctness signal.

## 6. Reporting

`scripts/long_report.py` prints, per (model, condition, episode) and in total:
violation, completion, abstention, exam score (+1 / 0 / −1 weighted), far-span and
trap violation, compactions and cost. Report violation **and** exam together — the
pilot showed that a memory condition can lower violation purely by abstaining.
