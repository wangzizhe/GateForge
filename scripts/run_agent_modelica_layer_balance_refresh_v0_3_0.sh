#!/usr/bin/env bash
set -euo pipefail

BASE_SPEC="${GATEFORGE_AGENT_LAYER_BALANCE_BASE_SPEC:-artifacts/agent_modelica_difficulty_layer_v0_2_6/spec.json}"
BASE_SUMMARY="${GATEFORGE_AGENT_LAYER_BALANCE_BASE_SUMMARY:-artifacts/agent_modelica_difficulty_layer_v0_2_6/summary.json}"
LAYER4_LANE_DIR="${GATEFORGE_AGENT_LAYER_BALANCE_LAYER4_LANE_DIR:-artifacts/agent_modelica_layer4_hard_lane_v0_3_0}"
OUT_DIR="${GATEFORGE_AGENT_LAYER_BALANCE_OUT_DIR:-artifacts/agent_modelica_difficulty_layer_v0_3_0}"

if [ ! -f "$LAYER4_LANE_DIR/summary.json" ]; then
  bash scripts/run_agent_modelica_layer4_hard_lane_v0_3_0.sh
fi

python3 -m gateforge.agent_modelica_layer_balance_refresh_v0_3_0 \
  --base-spec "$BASE_SPEC" \
  --base-summary "$BASE_SUMMARY" \
  --layer4-lane-dir "$LAYER4_LANE_DIR" \
  --out-dir "$OUT_DIR"
