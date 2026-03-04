#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_STRATEGY_AB_OUT_DIR:-artifacts/agent_modelica_strategy_ab_v1}"
TASKSET="${GATEFORGE_AGENT_STRATEGY_AB_TASKSET:-artifacts/agent_modelica_weekly_chain_v1/tasksets/taskset_$(date -u +%G-W%V).json}"
TREATMENT_PLAYBOOK="${GATEFORGE_AGENT_TREATMENT_PLAYBOOK:-artifacts/agent_modelica_repair_playbook_v1/playbook.json}"

if [ ! -f "$TASKSET" ]; then
  echo "Taskset not found: $TASKSET" >&2
  exit 1
fi
if [ ! -f "$TREATMENT_PLAYBOOK" ]; then
  echo "Treatment playbook not found: $TREATMENT_PLAYBOOK" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_strategy_ab_test_v1 \
  --taskset "$TASKSET" \
  --treatment-playbook "$TREATMENT_PLAYBOOK" \
  --mode mock \
  --out-dir "$OUT_DIR" \
  --out "$OUT_DIR/ab_summary.json" \
  --report-out "$OUT_DIR/ab_summary.md"

python3 -m gateforge.agent_modelica_strategy_promote_v1 \
  --ab-summary "$OUT_DIR/ab_summary.json" \
  --treatment-playbook "$TREATMENT_PLAYBOOK" \
  --out "$OUT_DIR/promoted_playbook.json" \
  --report-out "$OUT_DIR/promoted_playbook.md"

cat "$OUT_DIR/ab_summary.json"
