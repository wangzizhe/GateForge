#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${GATEFORGE_AGENT_LAYER4_HARD_LANE_OUT_DIR:-artifacts/agent_modelica_layer4_hard_lane_v0_3_0}"
FAMILY_SPEC="${GATEFORGE_AGENT_LAYER4_HARD_LANE_FAMILY_SPEC:-artifacts/agent_modelica_layer4_family_spec_v0_3_0/spec.json}"

python3 -m gateforge.agent_modelica_layer4_hard_lane_v0_3_0 \
  --family-spec "$FAMILY_SPEC" \
  --out-dir "$OUT_DIR"
