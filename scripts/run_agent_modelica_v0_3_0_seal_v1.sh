#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${GATEFORGE_AGENT_V0_3_0_SEAL_OUT_DIR:-artifacts/agent_modelica_v0_3_0_seal_v1}"

python3 -m gateforge.agent_modelica_v0_3_0_seal_v1 \
  --out-dir "$OUT_DIR"
