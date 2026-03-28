#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SPEC_PATH="${GATEFORGE_AGENT_LAYER4_FAMILY_SPEC:?GATEFORGE_AGENT_LAYER4_FAMILY_SPEC is required}"
OUT_PATH="${GATEFORGE_AGENT_LAYER4_FAMILY_SPEC_OUT:-artifacts/agent_modelica_layer4_family_spec_v1/summary.json}"
REPORT_OUT="${GATEFORGE_AGENT_LAYER4_FAMILY_SPEC_REPORT_OUT:-}"

python3 -m gateforge.agent_modelica_layer4_family_spec_v1 \
  --spec "$SPEC_PATH" \
  --out "$OUT_PATH" \
  ${REPORT_OUT:+--report-out "$REPORT_OUT"}
