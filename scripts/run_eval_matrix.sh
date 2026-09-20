#!/usr/bin/env bash
# The paper's evaluation matrix on the 100-episode long tier, in three stages.
#
#   stage 1  panel of backbones under compact-8k         -> pick the backbone
#   stage 2  the winner across the remaining conditions  -> the main table
#
# The panel runs under compact-8k, not full context, for two reasons.  It is the
# condition the main table uses, so the backbone is chosen under the regime it will
# be evaluated in -- long-context reasoning and memory maintenance do not rank models
# the same way (on the pilot, glm-5.3-flash scores exam -0.04 at full context and
# +0.10 under compact-8k).  And it costs a quarter as much: $47 against $203 for five
# models over 100 episodes.  Full context is a CEILING, not a competitor -- it answers
# "what if memory were not the problem" -- so it is run once, on the winner, inside
# stage 2.
#
#   scripts/run_eval_matrix.sh stage1 [EPISODE_IDS_FILE]          # the panel, compact-8k
#   scripts/run_eval_matrix.sh stage2 MODEL [EPISODE_IDS_FILE]    # the winner, everything else
#   scripts/run_eval_matrix.sh closed [EPISODE_IDS_FILE]          # gpt + claude + muse, full context
#   scripts/run_eval_matrix.sh report
#
# Environment (override on the command line):
#   OPEN_MODELS    comma-separated OpenRouter ids for the stage-1 panel
#   CLOSED_MODELS  comma-separated ids for the `closed` stage
#   PANEL_MEMORY   the condition stage 1 ranks under (default compact)
#   MEMORIES       comma-separated backends for stage 2 (built-ins: full compact compact2k none)
#   WINDOW         raw window in tokens (default 8000)
#   PERSIST        1 = one memory instance per world across its episodes (default 1)
#   WORKERS        parallel episodes/tasks (default 4)
# An EPISODE_IDS_FILE (one id per line) restricts a stage to a subsample; omit for all 100.
# Needs OPENROUTER_API_KEY:  set -a; . ~/.config/revoke/or.env; set +a
set -euo pipefail
cd "$(dirname "$0")/.."
DATA=data/long100
BLIND=$DATA/long100_blind.jsonl.gz
FULL=$DATA/long100_full.jsonl.gz
RUNS=runs/long100
: "${OPEN_MODELS:=z-ai/glm-5.3-flash,deepseek/deepseek-v4-flash,qwen/qwen3.7-flash,qwen/qwen3.8-flash,meta-llama/llama-4-maverick}"
: "${CLOSED_MODELS:=openai/gpt-5.5,anthropic/claude-opus-5}"
: "${PANEL_MEMORY:=compact}"                 # the condition stage 1 ranks under
: "${MEMORIES:=full,compact2k,none,mem0,memos,memp,dynamic_cheatsheet}"   # stage 2; compact comes from stage 1
: "${WINDOW:=8000}"
: "${PERSIST:=1}"
: "${WORKERS:=4}"
[ -f "$BLIND" ] || { echo "missing $BLIND -- gh release download v0.5-long100 --dir $DATA"; exit 1; }

ids_arg() {                      # -> "--items a,b,c" or nothing (BSD paste has no -sd)
  local f="${1:-}"; [ -n "$f" ] && [ -f "$f" ] && printf -- "--items %s" "$(tr '\n' ',' < "$f" | sed 's/,$//')" || true
}

case "${1:-}" in
  stage1)
    : "${OPENROUTER_API_KEY:?}"; mkdir -p "$RUNS/panel"
    P=""; [ "$PERSIST" = 1 ] && P="--persist"
    IFS=, read -ra MODELS <<< "$OPEN_MODELS"
    for m in "${MODELS[@]}"; do
      echo "=== panel: $m x $PANEL_MEMORY (window $WINDOW) ==="
      python3 eval/adapters/memory_runner.py --blind "$BLIND" --model "$m" --memory "$PANEL_MEMORY" \
        --window "$WINDOW" --workers "$WORKERS" --out "$RUNS/panel" $P $(ids_arg "${2:-}")
    done
    python3 scripts/pick_best.py --full "$FULL" --runs "$RUNS/panel" --mode "$PANEL_MEMORY" ;;
  closed)
    : "${OPENROUTER_API_KEY:?}"; mkdir -p "$RUNS/full_closed"
    python3 eval/adapters/openrouter_runner.py --blind "$BLIND" --models "$CLOSED_MODELS" --workers "$WORKERS" \
      --out "$RUNS/full_closed" $(ids_arg "${2:-}")
    python3 scripts/pick_best.py --full "$FULL" --runs "$RUNS/full_closed" ;;
  stage2)
    : "${OPENROUTER_API_KEY:?}"; MODEL="${2:?model id}"; mkdir -p "$RUNS/mem"
    P=""; [ "$PERSIST" = 1 ] && P="--persist"
    IFS=, read -ra MEMS <<< "$MEMORIES"
    for m in "${MEMS[@]}"; do
      echo "=== $MODEL x $m ==="
      W="$WINDOW"; MEM="$m"; CFG='{}'
      if [ "$m" = compact2k ]; then MEM=compact; W=2000; CFG='{"notes_cap": 1200}'; fi     # the pilot's 2k control
      python3 eval/adapters/memory_runner.py --blind "$BLIND" --model "$MODEL" --memory "$MEM" --window "$W" \
        --cfg "$CFG" --workers "$WORKERS" --out "$RUNS/mem" $P $(ids_arg "${3:-}")
    done ;;
  report)
    python3 scripts/long_report.py --full "$FULL" --runs "$RUNS"/panel "$RUNS"/full_closed "$RUNS"/mem 2>/dev/null | grep -E "^model|ALL" ;;
  *) sed -n '2,20p' "$0"; exit 1 ;;
esac
