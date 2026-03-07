#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L2_DUAL_GATE_OUT_DIR:-artifacts/agent_modelica_l2_dual_gate_v0}"
BENCHMARK_PATH="${GATEFORGE_AGENT_ELECTRICAL_TASKS_PATH:-benchmarks/agent_modelica_electrical_tasks_v0.json}"
SCALES="${GATEFORGE_AGENT_L2_DUAL_GATE_SCALES:-small,medium}"
MAX_TASKS="${GATEFORGE_AGENT_L2_DUAL_GATE_MAX_TASKS:-0}"
BACKEND="${GATEFORGE_AGENT_L2_DUAL_GATE_BACKEND:-openmodelica_docker}"
DOCKER_IMAGE="${GATEFORGE_AGENT_L2_DUAL_GATE_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"
TIMEOUT_SEC="${GATEFORGE_AGENT_L2_DUAL_GATE_TIMEOUT_SEC:-0}"
TIMEOUT_SMALL_SEC="${GATEFORGE_AGENT_L2_DUAL_GATE_TIMEOUT_SMALL_SEC:-180}"
TIMEOUT_MEDIUM_SEC="${GATEFORGE_AGENT_L2_DUAL_GATE_TIMEOUT_MEDIUM_SEC:-240}"
TIMEOUT_LARGE_SEC="${GATEFORGE_AGENT_L2_DUAL_GATE_TIMEOUT_LARGE_SEC:-420}"

mkdir -p "$OUT_DIR"
CACHE_DIR="$OUT_DIR/.omlibrary_cache"
mkdir -p "$CACHE_DIR"
CACHE_DIR="$(cd "$CACHE_DIR" && pwd)"

python3 -m gateforge.agent_modelica_l2_dual_gate_v0 \
  --benchmark "$BENCHMARK_PATH" \
  --scales "$SCALES" \
  --max-tasks "$MAX_TASKS" \
  --backend "$BACKEND" \
  --docker-image "$DOCKER_IMAGE" \
  --timeout-sec "$TIMEOUT_SEC" \
  --timeout-small-sec "$TIMEOUT_SMALL_SEC" \
  --timeout-medium-sec "$TIMEOUT_MEDIUM_SEC" \
  --timeout-large-sec "$TIMEOUT_LARGE_SEC" \
  --cache-dir "$CACHE_DIR" \
  --modelica-dir "$OUT_DIR/modelica" \
  --records-out "$OUT_DIR/records.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

cat "$OUT_DIR/summary.json"
