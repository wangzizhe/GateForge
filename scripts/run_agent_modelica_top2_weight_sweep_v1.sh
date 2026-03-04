#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_TOP2_SWEEP_OUT_DIR:-artifacts/agent_modelica_top2_weight_sweep_v1}"
WEEK_TAG="${GATEFORGE_AGENT_WEEK_TAG:-$(date -u +%G-W%V)}"
TASKSET="${GATEFORGE_AGENT_TOP2_TASKSET:-artifacts/agent_modelica_weekly_chain_v1/tasksets/evidence_taskset_${WEEK_TAG}.json}"
BASE_PLAYBOOK="${GATEFORGE_AGENT_BASE_PLAYBOOK:-artifacts/agent_modelica_repair_playbook_v1/playbook.json}"
WEIGHT_TRIPLES="${GATEFORGE_AGENT_TOP2_SWEEP_WEIGHT_TRIPLES:-0.8,0.2,0.8;0.7,0.3,0.8;0.6,0.4,0.8}"

if [ ! -f "$TASKSET" ]; then
  echo "Taskset not found: $TASKSET" >&2
  exit 1
fi
if [ ! -f "$BASE_PLAYBOOK" ]; then
  echo "Base playbook not found: $BASE_PLAYBOOK" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
python3 -m gateforge.agent_modelica_top2_weight_sweep_v1 \
  --taskset "$TASKSET" \
  --base-playbook "$BASE_PLAYBOOK" \
  --weight-triples "$WEIGHT_TRIPLES" \
  --out-dir "$OUT_DIR" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

cat "$OUT_DIR/summary.json"
