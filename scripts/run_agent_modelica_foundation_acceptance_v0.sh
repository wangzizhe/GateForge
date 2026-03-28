#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SPEC_PATH="${GATEFORGE_AGENT_FOUNDATION_ACCEPTANCE_SPEC:?GATEFORGE_AGENT_FOUNDATION_ACCEPTANCE_SPEC is required}"
OUT_PATH="${GATEFORGE_AGENT_FOUNDATION_ACCEPTANCE_OUT:-artifacts/agent_modelica_foundation_acceptance_v0/summary.json}"
REPORT_OUT="${GATEFORGE_AGENT_FOUNDATION_ACCEPTANCE_REPORT_OUT:-}"

python3 -m gateforge.agent_modelica_foundation_acceptance_v0 \
  --spec "$SPEC_PATH" \
  --out "$OUT_PATH" \
  ${REPORT_OUT:+--report-out "$REPORT_OUT"}
