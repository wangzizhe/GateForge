#!/usr/bin/env bash
set -euo pipefail

SOURCE_PACK="${GATEFORGE_AGENT_PLANNER_SENSITIVE_SOURCE_PACK:-assets_private/agent_modelica_track_a_valid32_fixture_v1/hardpack_frozen.json}"
OUT_DIR="${GATEFORGE_AGENT_PLANNER_SENSITIVE_OUT_DIR:-artifacts/agent_modelica_planner_sensitive_pack_builder_v1}"
OUT_PACK="${GATEFORGE_AGENT_PLANNER_SENSITIVE_OUT_PACK:-$OUT_DIR/hardpack_planner_sensitive.json}"
OUT_SUMMARY="${GATEFORGE_AGENT_PLANNER_SENSITIVE_OUT_SUMMARY:-$OUT_DIR/summary.json}"
MAX_CASES="${GATEFORGE_AGENT_PLANNER_SENSITIVE_MAX_CASES:-24}"
PLANNER_INVOKED_TARGET_PCT="${GATEFORGE_AGENT_PLANNER_SENSITIVE_TARGET_PCT:-50}"

IFS=':' read -r -a GF_RESULTS_ARRAY <<< "${GATEFORGE_AGENT_PLANNER_SENSITIVE_GF_RESULTS:-}"

ARGS=(
  --source-pack "$SOURCE_PACK"
  --out-pack "$OUT_PACK"
  --out-summary "$OUT_SUMMARY"
  --max-cases "$MAX_CASES"
  --planner-invoked-target-pct "$PLANNER_INVOKED_TARGET_PCT"
)

for path in "${GF_RESULTS_ARRAY[@]}"; do
  if [ -n "$path" ]; then
    ARGS+=(--gf-results "$path")
  fi
done

python3 -m gateforge.agent_modelica_planner_sensitive_pack_builder_v1 "${ARGS[@]}"
