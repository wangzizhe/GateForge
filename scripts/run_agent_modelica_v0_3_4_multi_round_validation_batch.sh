#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WORKORDER_PATH="${GATEFORGE_AGENT_V034_MULTI_ROUND_WORKORDER:-artifacts/agent_modelica_multi_round_validation_workorder_v0_3_4_current/summary.json}"
REFRESHED_TASKSET_PATH="${GATEFORGE_AGENT_V034_MULTI_ROUND_REFRESHED_TASKSET:-artifacts/agent_modelica_track_c_candidate_attribution_refresh_v0_3_3_w15a_w15b/taskset_candidates_refreshed.json}"
OUT_DIR="${GATEFORGE_AGENT_V034_MULTI_ROUND_VALIDATION_OUT_DIR:-artifacts/agent_modelica_v0_3_4_multi_round_validation_local}"
MAX_ROUNDS="${GATEFORGE_AGENT_V034_MULTI_ROUND_MAX_ROUNDS:-3}"
TIMEOUT_SEC="${GATEFORGE_AGENT_V034_MULTI_ROUND_TIMEOUT_SEC:-180}"

mkdir -p "$OUT_DIR"

python3 - "$WORKORDER_PATH" "$REFRESHED_TASKSET_PATH" <<'PY' | while IFS=$'\t' read -r task_id failure_type expected_stage source_model_path mutated_model_path source_library_path source_package_name source_library_model_path source_qualified_model_name; do
import json
import sys
from pathlib import Path

workorder_path = Path(sys.argv[1])
refreshed_path = Path(sys.argv[2])
workorder = json.loads(workorder_path.read_text(encoding="utf-8"))
refreshed = json.loads(refreshed_path.read_text(encoding="utf-8"))
selected_ids = [str(item.get("task_id") or "") for item in (workorder.get("tasks") or []) if isinstance(item, dict)]
task_map = {
    str(task.get("task_id") or ""): task
    for task in (refreshed.get("tasks") or [])
    if isinstance(task, dict)
}
for task_id in selected_ids:
    task = task_map.get(task_id)
    if not isinstance(task, dict):
        continue
    meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
    fields = [
        task_id,
        str(task.get("failure_type") or ""),
        str(task.get("expected_stage") or "simulate"),
        str(task.get("source_model_path") or ""),
        str(task.get("mutated_model_path") or ""),
        str(meta.get("local_path") or ""),
        str(meta.get("package_name") or ""),
        str(meta.get("model_path") or ""),
        str(meta.get("qualified_model_name") or ""),
    ]
    print("\t".join(fields))
PY
  out_path="$OUT_DIR/${task_id}.json"
  env \
    GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR=1 \
    python3 -m gateforge.agent_modelica_live_executor_gemini_v1 \
      --task-id "${task_id}_v034_multiround_validation" \
      --failure-type "$failure_type" \
      --expected-stage "$expected_stage" \
      --source-model-path "$source_model_path" \
      --mutated-model-path "$mutated_model_path" \
      --source-library-path "$source_library_path" \
      --source-package-name "$source_package_name" \
      --source-library-model-path "$source_library_model_path" \
      --source-qualified-model-name "$source_qualified_model_name" \
      --backend openmodelica_docker \
      --planner-backend gemini \
      --max-rounds "$MAX_ROUNDS" \
      --timeout-sec "$TIMEOUT_SEC" \
      --out "$out_path"
  printf 'wrote %s\n' "$out_path"
done
