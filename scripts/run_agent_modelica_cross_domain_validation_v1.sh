#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SPEC_PATH="${GATEFORGE_AGENT_CROSS_DOMAIN_VALIDATION_SPEC:-artifacts/agent_modelica_cross_domain_validation_v1/spec.json}"
OUT_PATH="${GATEFORGE_AGENT_CROSS_DOMAIN_VALIDATION_OUT:-artifacts/agent_modelica_cross_domain_validation_v1/summary.json}"

python3 -m gateforge.agent_modelica_cross_domain_validation_v1 \
  --spec "$SPEC_PATH" \
  --out "$OUT_PATH"

cat "$OUT_PATH"
