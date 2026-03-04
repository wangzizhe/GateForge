#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_EVIDENCE_BASELINE_OUT_DIR:-artifacts/agent_modelica_evidence_baseline_v1}"
TASKSET_SOURCE="${GATEFORGE_AGENT_EVIDENCE_TASKSET_SOURCE:-artifacts/agent_modelica_weekly_chain_v1/tasksets/taskset_$(date -u +%G-W%V).json}"
REPAIR_PLAYBOOK="${GATEFORGE_AGENT_REPAIR_PLAYBOOK:-artifacts/agent_modelica_repair_playbook_v1/playbook.json}"

if [ ! -f "$TASKSET_SOURCE" ]; then
  echo "Taskset source not found: $TASKSET_SOURCE" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_evidence_taskset_builder_v1 \
  --taskset "$TASKSET_SOURCE" \
  --include-scales medium,large \
  --per-scale-limit 20 \
  --taskset-out "$OUT_DIR/evidence_taskset.json" \
  --out "$OUT_DIR/evidence_taskset_summary.json" \
  --report-out "$OUT_DIR/evidence_taskset_summary.md"

python3 -m gateforge.agent_modelica_layered_baseline_v1 \
  --taskset-in "$OUT_DIR/evidence_taskset.json" \
  --scales medium,large \
  --failure-types model_check_error,simulate_error,semantic_regression \
  --run-mode evidence \
  --repair-playbook "$REPAIR_PLAYBOOK" \
  --out-dir "$OUT_DIR/baseline" \
  --out "$OUT_DIR/baseline/summary.json" \
  --report-out "$OUT_DIR/baseline/summary.md"

cat "$OUT_DIR/baseline/summary.json"
