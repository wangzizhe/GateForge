#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_OUT_DIR:-artifacts/agent_modelica_difficulty_layer_sidecar_builder_v1}"
SUBSTRATE="${GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_SUBSTRATE:-}"
OUT_SIDECAR="${GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_OUT_PATH:-$OUT_DIR/layer_metadata.json}"
OUT_SUMMARY="${GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_OUT_SUMMARY:-$OUT_DIR/summary.json}"
HINT_RULES="${GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_HINT_RULES:-}"
OVERRIDE_PATH="${GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_OVERRIDE:-}"

RESULTS_ENV="${GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_RESULTS:-}"
RESULTS_ARRAY=()
if [ -n "$RESULTS_ENV" ]; then
  IFS=':' read -r -a RESULTS_ARRAY <<< "$RESULTS_ENV"
fi

if [ -z "$SUBSTRATE" ]; then
  echo "Missing GATEFORGE_AGENT_DIFFICULTY_LAYER_SIDECAR_SUBSTRATE" >&2
  exit 1
fi

ARGS=(
  --substrate "$SUBSTRATE"
  --out-sidecar "$OUT_SIDECAR"
  --out-summary "$OUT_SUMMARY"
)

if [ -n "$HINT_RULES" ]; then
  ARGS+=(--hint-rules "$HINT_RULES")
fi

if [ -n "$OVERRIDE_PATH" ]; then
  ARGS+=(--override "$OVERRIDE_PATH")
fi

if [ ${#RESULTS_ARRAY[@]} -gt 0 ]; then
  for path in "${RESULTS_ARRAY[@]}"; do
    if [ -n "$path" ]; then
      ARGS+=(--results "$path")
    fi
  done
fi

python3 -m gateforge.agent_modelica_difficulty_layer_sidecar_builder_v1 "${ARGS[@]}"
