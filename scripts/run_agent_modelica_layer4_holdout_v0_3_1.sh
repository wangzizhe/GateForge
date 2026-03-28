#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${GATEFORGE_AGENT_LAYER4_HOLDOUT_OUT_DIR:-artifacts/agent_modelica_layer4_holdout_v0_3_1}"

python3 -m gateforge.agent_modelica_layer4_holdout_v0_3_1 \
  --out-dir "$OUT_DIR"
