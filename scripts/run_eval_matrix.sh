#!/usr/bin/env bash
# The paper's evaluation matrix on the 100-episode long tier, in three stages.
#
#   stage 1  open flash-tier panel, full context          -> pick the best open backbone
#   stage 2  closed panel (gpt + claude), full context    -> pick the best closed backbone
#   stage 3  memory systems on each chosen backbone, one continuous pass per episode
#
#   scripts/run_eval_matrix.sh stage1 [EPISODE_IDS_FILE]
#   scripts/run_eval_matrix.sh stage2 [EPISODE_IDS_FILE]
#   scripts/run_eval_matrix.sh stage3 MODEL [EPISODE_IDS_FILE]
#   scripts/run_eval_matrix.sh report
#
# Environment (override on the command line):
#   OPEN_MODELS    comma-separated OpenRouter ids for stage 1
#   CLOSED_MODELS  comma-separated ids for stage 2
#   MEMORIES       comma-separated backends for stage 3 (built-ins: full compact compact2k none)
#   WINDOW         raw window in tokens for stage 3 (default 8000)
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
: "${MEMORIES:=full,compact,compact2k,none,mem0,memos,memp,dynamic_cheatsheet}"
: "${WINDOW:=8000}"
: "${PERSIST:=1}"
: "${WORKERS:=4}"
[ -f "$BLIND" ] || { echo "missing $BLIND -- gh release download v0.5-long100 --dir $DATA"; exit 1; }

ids_arg() {                      # -> "--items a,b,c" or nothing (BSD paste has no -sd)
  local f="${1:-}"; [ -n "$f" ] && [ -f "$f" ] && printf -- "--items %s" "$(tr '\n' ',' < "$f" | sed 's/,$//')" || true
}

case "${1:-}" in
  stage1)
    : "${OPENROUTER_API_KEY:?}"; mkdir -p "$RUNS/full_open"
    python3 eval/adapters/openrouter_runner.py --blind "$BLIND" --models "$OPEN_MODELS" --workers "$WORKERS" \
      --out "$RUNS/full_open" $(ids_arg "${2:-}")
    python3 scripts/pick_best.py --full "$FULL" --runs "$RUNS/full_open" ;;
  stage2)
    : "${OPENROUTER_API_KEY:?}"; mkdir -p "$RUNS/full_closed"
    python3 eval/adapters/openrouter_runner.py --blind "$BLIND" --models "$CLOSED_MODELS" --workers "$WORKERS" \
      --out "$RUNS/full_closed" $(ids_arg "${2:-}")
    python3 scripts/pick_best.py --full "$FULL" --runs "$RUNS/full_closed" ;;
  stage3)
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
    python3 scripts/long_report.py --full "$FULL" --runs "$RUNS"/full_open "$RUNS"/full_closed "$RUNS"/mem 2>/dev/null | grep -E "^model|ALL" ;;
  *) sed -n '2,20p' "$0"; exit 1 ;;
esac
