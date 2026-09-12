#!/usr/bin/env bash
# Long-tier pilot: build five 300k-1M episodes, run scripted baselines, run the
# continuous-episode conditions, grade.
#
#   scripts/run_long_pilot.sh build          # episodes -> data/long/
#   scripts/run_long_pilot.sh baselines      # oracle/stale/recency/random/refuse
#   scripts/run_long_pilot.sh run MODEL      # compact b2000/k55 and b8000/k93 on all five
#   scripts/run_long_pilot.sh grade          # episode_report over runs/long/
#
# Model runs need OPENROUTER_API_KEY:  set -a; . ~/.config/revoke/or.env; set +a
set -euo pipefail
cd "$(dirname "$0")/.."
PLAN="clinical_ward=300000,devops_release=450000,design_system=600000,companion=800000,game_narrative=1000000"
DATA=data/long
RUNS=runs/long

case "${1:-}" in
  build)
    python3 eval/build_long.py --plan "$PLAN" --probes 10 --seed 11 --out "$DATA" ;;
  baselines)
    mkdir -p "$RUNS/baselines"
    for pol in oracle stale recency random refuse; do
      python3 scripts/baselines.py --dataset "$DATA/long_full.jsonl" --policy "$pol" \
        --out "$RUNS/baselines/$pol.jsonl" >/dev/null
    done
    python3 - <<'PY'
import json, sys
sys.path.insert(0, "eval"); sys.path.insert(0, ".")
from grade import grade_item, exam
items = {json.loads(l)["id"]: json.loads(l) for l in open("data/long/long_full.jsonl")}
print(f"{'policy':<9}" + "".join(f"{k.split('_', 2)[2][:14]:>16}" for k in items))
for pol in ("oracle", "stale", "recency", "random", "refuse"):
    row = []
    for line in open(f"runs/long/baselines/{pol}.jsonl"):
        r = json.loads(line); g = grade_item(items[r["id"]], r); e = exam(g["probes"])
        v = sum(x["violation"] for x in g["probes"]) / len(g["probes"])
        row.append(f"v{v:.2f} ex{e['score']:+.2f}")
    print(f"{pol:<9}" + "".join(f"{x:>16}" for x in row))
PY
    ;;
  run)
    MODEL="${2:?model id, e.g. z-ai/glm-5.3-flash}"
    : "${OPENROUTER_API_KEY:?set OPENROUTER_API_KEY}"
    mkdir -p "$RUNS/episodes"
    python3 eval/adapters/episode_runner.py --blind "$DATA/long_blind.jsonl" --models "$MODEL" \
      --modes compact --budget 2000 --keep-frac 0.55 --workers 5 --out "$RUNS/episodes" &
    python3 eval/adapters/episode_runner.py --blind "$DATA/long_blind.jsonl" --models "$MODEL" \
      --modes compact --budget 8000 --keep-frac 0.93 --workers 5 --out "$RUNS/episodes" &
    wait ;;
  grade)
    python3 scripts/episode_report.py --full "$DATA/long_full.jsonl" --runs "$RUNS/episodes" ;;
  *)
    sed -n '2,12p' "$0"; exit 1 ;;
esac
