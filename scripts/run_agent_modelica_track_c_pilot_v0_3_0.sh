#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${GATEFORGE_AGENT_TRACK_C_PILOT_OUT_DIR:-artifacts/agent_modelica_track_c_pilot_v0_3_0}"
ARGS=(--out-dir "$OUT_DIR")
if [ -n "${GATEFORGE_AGENT_TRACK_C_BUDGET_RESULTS:-}" ]; then
  IFS=':' read -r -a BUDGET_RESULTS_ARRAY <<< "${GATEFORGE_AGENT_TRACK_C_BUDGET_RESULTS}"
  for path in "${BUDGET_RESULTS_ARRAY[@]}"; do
    if [ -n "$path" ]; then
      ARGS+=(--budget-results "$path")
    fi
  done
fi

python3 -m gateforge.agent_modelica_track_c_pilot_v0_3_0 "${ARGS[@]}"
