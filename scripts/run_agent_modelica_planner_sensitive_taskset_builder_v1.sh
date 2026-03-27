#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${GATEFORGE_AGENT_PLANNER_SENSITIVE_TASKSET_OUT_DIR:-artifacts/agent_modelica_planner_sensitive_taskset_builder_v1}"
OUT_TASKSET="${GATEFORGE_AGENT_PLANNER_SENSITIVE_TASKSET_OUT_TASKSET:-$OUT_DIR/taskset_frozen.json}"
OUT_SUMMARY="${GATEFORGE_AGENT_PLANNER_SENSITIVE_TASKSET_OUT_SUMMARY:-$OUT_DIR/summary.json}"
MAX_TASKS="${GATEFORGE_AGENT_PLANNER_SENSITIVE_TASKSET_MAX_TASKS:-24}"
PLANNER_INVOKED_TARGET_PCT="${GATEFORGE_AGENT_PLANNER_SENSITIVE_TASKSET_TARGET_PCT:-50}"

IFS=':' read -r -a RESULTS_ARRAY <<< "${GATEFORGE_AGENT_PLANNER_SENSITIVE_TASKSET_RESULTS:-}"
IFS=':' read -r -a TASKSET_ARRAY <<< "${GATEFORGE_AGENT_PLANNER_SENSITIVE_TASKSET_SOURCE_TASKSETS:-}"

ARGS=(
  --out-taskset "$OUT_TASKSET"
  --out-summary "$OUT_SUMMARY"
  --max-tasks "$MAX_TASKS"
  --planner-invoked-target-pct "$PLANNER_INVOKED_TARGET_PCT"
)

for path in "${RESULTS_ARRAY[@]}"; do
  if [ -n "$path" ]; then
    ARGS+=(--results "$path")
  fi
done
for path in "${TASKSET_ARRAY[@]}"; do
  if [ -n "$path" ]; then
    ARGS+=(--taskset "$path")
  fi
done

python3 -m gateforge.agent_modelica_planner_sensitive_taskset_builder_v1 "${ARGS[@]}"
