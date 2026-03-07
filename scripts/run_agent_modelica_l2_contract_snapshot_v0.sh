#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L2_CONTRACT_OUT_DIR:-assets_private/agent_modelica_l2_contract_snapshot_v0}"
BENCHMARK_PATH="${GATEFORGE_AGENT_ELECTRICAL_TASKS_PATH:-benchmarks/agent_modelica_electrical_tasks_v0.json}"
SAMPLE_COUNT="${GATEFORGE_AGENT_L2_CONTRACT_SAMPLE_COUNT:-3}"
SAMPLE_SCALES="${GATEFORGE_AGENT_L2_CONTRACT_SAMPLE_SCALES:-small,medium}"

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_l2_contract_snapshot_v0 \
  --benchmark "$BENCHMARK_PATH" \
  --sample-count "$SAMPLE_COUNT" \
  --sample-scales "$SAMPLE_SCALES" \
  --out "$OUT_DIR/contract_snapshot.json" \
  --sample-out "$OUT_DIR/sample_ir_tasks.json" \
  --report-out "$OUT_DIR/contract_snapshot.md"

cat "$OUT_DIR/contract_snapshot.json"
