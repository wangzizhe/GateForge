#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_PATH="${GATEFORGE_AGENT_CROSS_DOMAIN_VALIDATION_SPEC_OUT:-artifacts/agent_modelica_cross_domain_validation_v1/spec.json}"
TRACK_MANIFEST="${GATEFORGE_AGENT_CROSS_DOMAIN_TRACK_MANIFEST:-data/agent_modelica_cross_domain_track_manifest_v1.json}"
EXPECTATION_TEMPLATE="${GATEFORGE_AGENT_CROSS_DOMAIN_EXPECTATION_TEMPLATE:-data/agent_modelica_cross_domain_validation_spec_template_v1.json}"

MATRIX_SUMMARIES=()
if [ -n "${GATEFORGE_AGENT_CROSS_DOMAIN_MATRIX_SUMMARIES:-}" ]; then
  IFS=':' read -r -a RAW <<< "$GATEFORGE_AGENT_CROSS_DOMAIN_MATRIX_SUMMARIES"
  for item in "${RAW[@]}"; do
    if [ -n "$item" ]; then
      MATRIX_SUMMARIES+=(--matrix-summary "$item")
    fi
  done
fi

python3 -m gateforge.agent_modelica_cross_domain_validation_spec_builder_v1 \
  "${MATRIX_SUMMARIES[@]}" \
  --track-manifest "$TRACK_MANIFEST" \
  --expectation-template "$EXPECTATION_TEMPLATE" \
  --out "$OUT_PATH"

cat "$OUT_PATH"
