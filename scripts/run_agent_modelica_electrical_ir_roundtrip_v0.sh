#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BENCHMARK_PATH="${GATEFORGE_AGENT_ELECTRICAL_TASKS_PATH:-benchmarks/agent_modelica_electrical_tasks_v0.json}"
OUT_DIR="${GATEFORGE_AGENT_ELECTRICAL_ROUNDTRIP_OUT_DIR:-artifacts/agent_modelica_electrical_ir_roundtrip_v0}"
MAX_TASKS="${GATEFORGE_AGENT_ELECTRICAL_ROUNDTRIP_MAX_TASKS:-0}"

mkdir -p "$OUT_DIR"

ARGS=(
  --benchmark "$BENCHMARK_PATH"
  --modelica-dir "$OUT_DIR/modelica"
  --records-out "$OUT_DIR/records.json"
  --out "$OUT_DIR/summary.json"
)

if [ "$MAX_TASKS" != "0" ]; then
  ARGS+=(--max-tasks "$MAX_TASKS")
fi

python3 -m gateforge.agent_modelica_electrical_ir_roundtrip_v0 "${ARGS[@]}"
