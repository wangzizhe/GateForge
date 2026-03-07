#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_OMC_ADAPTER_SMOKE_OUT_DIR:-artifacts/agent_modelica_omc_adapter_smoke_v0}"
MODEL_PATH="${GATEFORGE_AGENT_OMC_ADAPTER_SMOKE_MODEL_PATH:-artifacts/agent_modelica_electrical_live_focus_boost_v0_smoke_r6/source_models/small_rc_constant_v0.mo}"
TIMEOUT_SEC="${GATEFORGE_AGENT_OMC_ADAPTER_SMOKE_TIMEOUT_SEC:-180}"

mkdir -p "$OUT_DIR"
if [ ! -f "$MODEL_PATH" ]; then
  echo "Missing model path for smoke: $MODEL_PATH" >&2
  exit 1
fi

python3 -m gateforge.agent_modelica_live_executor_gemini_v1 \
  --task-id "l2-omc-adapter-smoke" \
  --failure-type "none" \
  --expected-stage "check" \
  --source-model-path "$MODEL_PATH" \
  --mutated-model-path "$MODEL_PATH" \
  --max-rounds 1 \
  --timeout-sec "$TIMEOUT_SEC" \
  --planner-backend rule \
  --backend openmodelica_docker \
  --out "$OUT_DIR/smoke.json"

cat "$OUT_DIR/smoke.json"
