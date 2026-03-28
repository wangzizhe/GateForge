#!/usr/bin/env bash
set -euo pipefail

SPEC_PATH="${GATEFORGE_AGENT_DIFFICULTY_LAYER_SUMMARY_SPEC:-}"
OUT_PATH="${GATEFORGE_AGENT_DIFFICULTY_LAYER_SUMMARY_OUT:-artifacts/agent_modelica_difficulty_layer_summary_v1/summary.json}"
REPORT_PATH="${GATEFORGE_AGENT_DIFFICULTY_LAYER_SUMMARY_REPORT:-}"

if [ -z "$SPEC_PATH" ]; then
  echo "Missing GATEFORGE_AGENT_DIFFICULTY_LAYER_SUMMARY_SPEC" >&2
  exit 1
fi

python3 -m gateforge.agent_modelica_difficulty_layer_summary_v1 \
  --spec "$SPEC_PATH" \
  --out "$OUT_PATH" \
  --report-out "$REPORT_PATH"
