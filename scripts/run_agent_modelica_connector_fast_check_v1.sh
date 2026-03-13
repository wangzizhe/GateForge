#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TASKSET="${GATEFORGE_AGENT_CONNECTOR_FAST_CHECK_TASKSET:-artifacts/agent_modelica_electrical_realism_frozen_taskset_v1/taskset_frozen.json}"
OUT_DIR="${GATEFORGE_AGENT_CONNECTOR_FAST_CHECK_OUT_DIR:-artifacts/agent_modelica_connector_fast_check_v1}"
BACKEND="${GATEFORGE_AGENT_CONNECTOR_FAST_CHECK_BACKEND:-openmodelica_docker}"
DOCKER_IMAGE="${GATEFORGE_AGENT_CONNECTOR_FAST_CHECK_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"
TIMEOUT_SEC="${GATEFORGE_AGENT_CONNECTOR_FAST_CHECK_TIMEOUT_SEC:-30}"

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_connector_fast_check_v1 \
  --taskset "$TASKSET" \
  --backend "$BACKEND" \
  --docker-image "$DOCKER_IMAGE" \
  --timeout-sec "$TIMEOUT_SEC" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"
