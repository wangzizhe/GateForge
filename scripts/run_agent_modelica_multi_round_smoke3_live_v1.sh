#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_MULTI_ROUND_SMOKE3_OUT_DIR:-artifacts/agent_modelica_multi_round_smoke3_live_v1}"
RUN_ID="${GATEFORGE_AGENT_MULTI_ROUND_SMOKE3_RUN_ID:-$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).strftime("multi_round_smoke3_%Y%m%dT%H%M%SZ"))
PY
)}"
RUN_ROOT="${GATEFORGE_AGENT_MULTI_ROUND_SMOKE3_RUN_ROOT:-$OUT_DIR/runs/$RUN_ID}"
UPDATE_LATEST="${GATEFORGE_AGENT_MULTI_ROUND_SMOKE3_UPDATE_LATEST:-1}"

MANIFEST_PATH="${GATEFORGE_AGENT_MULTI_ROUND_FAILURE_MANIFEST:-assets_private/agent_modelica_multi_round_failure_pack_v1/manifest.json}"
SMOKE_TASK_IDS="${GATEFORGE_AGENT_MULTI_ROUND_SMOKE_TASK_IDS:-}"
FAILURE_TYPES="${GATEFORGE_AGENT_MULTI_ROUND_FAILURE_TYPES:-cascading_structural_failure,coupled_conflict_failure,false_friend_patch_trap}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_MULTI_ROUND_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_MULTI_ROUND_SPLIT_SEED:-agent_modelica_multi_round_failure_taskset_v1}"
EXCLUDE_TASK_IDS_JSON="${GATEFORGE_AGENT_MULTI_ROUND_EXCLUDE_TASK_IDS_JSON:-}"
MAX_ROUNDS="${GATEFORGE_AGENT_MULTI_ROUND_MAX_ROUNDS:-3}"
MAX_TIME_SEC="${GATEFORGE_AGENT_MULTI_ROUND_MAX_TIME_SEC:-300}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_MULTI_ROUND_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_MULTI_ROUND_LIVE_TIMEOUT_SEC:-300}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_MULTI_ROUND_LIVE_MAX_OUTPUT_CHARS:-2400}"
PER_TASK_TIME_BUDGET_SEC="${GATEFORGE_AGENT_MULTI_ROUND_SMOKE3_PER_TASK_TIME_BUDGET_SEC:-300}"
MIN_TASKS_WITHIN_BUDGET="${GATEFORGE_AGENT_MULTI_ROUND_SMOKE3_MIN_TASKS_WITHIN_BUDGET:-2}"
PLANNER_BACKEND="${GATEFORGE_AGENT_LIVE_PLANNER_BACKEND:-auto}"
OM_BACKEND="${GATEFORGE_AGENT_LIVE_OM_BACKEND:-openmodelica_docker}"
OM_DOCKER_IMAGE="${GATEFORGE_AGENT_LIVE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"

DEFAULT_LIVE_EXECUTOR_CMD="python3 -m gateforge.agent_modelica_live_executor_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --source-library-path \"__SOURCE_LIBRARY_PATH__\" --source-package-name \"__SOURCE_PACKAGE_NAME__\" --source-library-model-path \"__SOURCE_LIBRARY_MODEL_PATH__\" --source-qualified-model-name \"__SOURCE_QUALIFIED_MODEL_NAME__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${PLANNER_BACKEND}\" --backend \"${OM_BACKEND}\" --docker-image \"${OM_DOCKER_IMAGE}\""
LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_LIVE_EXECUTOR_CMD:-$DEFAULT_LIVE_EXECUTOR_CMD}"

CHALLENGE_DIR="$RUN_ROOT/challenge"
SMOKE_TASKSET_DIR="$RUN_ROOT/smoke_taskset"
BASELINE_DIR="$RUN_ROOT/baseline_off_live"
SMOKE_SUMMARY_PATH="$RUN_ROOT/smoke_summary.json"
FINAL_RUN_SUMMARY_PATH="$RUN_ROOT/final_run_summary.json"

mkdir -p "$OUT_DIR" "$OUT_DIR/runs" "$RUN_ROOT" "$CHALLENGE_DIR" "$SMOKE_TASKSET_DIR" "$BASELINE_DIR"

python3 - "$RUN_ROOT/run_manifest.json" "$RUN_ID" "$RUN_ROOT" "$MANIFEST_PATH" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
path, run_id, run_root, manifest = sys.argv[1:]
Path(path).write_text(json.dumps({
    "schema_version": "agent_modelica_multi_round_smoke3_run_manifest_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_id": run_id,
    "run_root": run_root,
    "manifest_path": manifest,
}, indent=2), encoding="utf-8")
PY

challenge_cmd=(
  python3 -m gateforge.agent_modelica_multi_round_failure_taskset_v1
  --manifest "$MANIFEST_PATH"
  --out-dir "$CHALLENGE_DIR"
  --failure-types "$FAILURE_TYPES"
  --holdout-ratio "$HOLDOUT_RATIO"
  --seed "$SPLIT_SEED"
)
if [ -n "$EXCLUDE_TASK_IDS_JSON" ]; then
  challenge_cmd+=(--exclude-task-ids-json "$EXCLUDE_TASK_IDS_JSON")
fi
"${challenge_cmd[@]}"

resolve_smoke_task_ids() {
  if [ -n "$SMOKE_TASK_IDS" ]; then
    printf '%s' "$SMOKE_TASK_IDS"
    return 0
  fi
  python3 - <<'PY' "$CHALLENGE_DIR/taskset_frozen.json"
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
tasks = [row for row in (payload.get("tasks") or []) if isinstance(row, dict)]
selected = []
selected_libraries = set()
selected_models = set()

def library_key(row):
    source_meta = row.get("source_meta") if isinstance(row.get("source_meta"), dict) else {}
    return str(source_meta.get("library_id") or row.get("source_library") or "").strip().lower()

def model_key(row):
    source_meta = row.get("source_meta") if isinstance(row.get("source_meta"), dict) else {}
    return str(source_meta.get("model_id") or row.get("source_qualified_model_name") or "").strip().lower()

for failure_type in ["cascading_structural_failure", "coupled_conflict_failure", "false_friend_patch_trap"]:
    candidates = [row for row in tasks if str(row.get("failure_type") or "").strip().lower() == failure_type]
    candidates.sort(
        key=lambda row: (
            1 if library_key(row) in selected_libraries else 0,
            1 if model_key(row) in selected_models else 0,
            -int(row.get("source_rewrite_count") or 0),
            -int(row.get("mutation_span_count") or 0),
            -float(row.get("failure_signal_delay_sec") or 0.0),
            str(row.get("task_id") or ""),
        )
    )
    if candidates:
        chosen = candidates[0]
        selected.append(str(chosen.get("task_id") or "").strip())
        selected_libraries.add(library_key(chosen))
        selected_models.add(model_key(chosen))
print(",".join([item for item in selected if item]))
PY
}

python3 -m gateforge.agent_modelica_unknown_library_smoke_taskset_v1 \
  --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
  --task-ids-csv "$(resolve_smoke_task_ids)" \
  --out-dir "$SMOKE_TASKSET_DIR"

python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset "$SMOKE_TASKSET_DIR/taskset_frozen.json" \
  --mode live \
  --max-rounds "$MAX_ROUNDS" \
  --max-time-sec "$MAX_TIME_SEC" \
  --runtime-threshold "$RUNTIME_THRESHOLD" \
  --live-executor-cmd "$LIVE_EXECUTOR_CMD" \
  --live-timeout-sec "$LIVE_TIMEOUT_SEC" \
  --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS" \
  --records-jsonl "$BASELINE_DIR/records.jsonl" \
  --results-out "$BASELINE_DIR/results.json" \
  --out "$BASELINE_DIR/summary.json"

python3 -m gateforge.agent_modelica_unknown_library_smoke3_summary_v1 \
  --taskset "$SMOKE_TASKSET_DIR/taskset_frozen.json" \
  --results "$BASELINE_DIR/results.json" \
  --records-jsonl "$BASELINE_DIR/records.jsonl" \
  --per-task-time-budget-sec "$PER_TASK_TIME_BUDGET_SEC" \
  --min-tasks-within-budget "$MIN_TASKS_WITHIN_BUDGET" \
  --out "$SMOKE_SUMMARY_PATH"

python3 - "$FINAL_RUN_SUMMARY_PATH" "$SMOKE_SUMMARY_PATH" "$RUN_ID" "$RUN_ROOT" "$OUT_DIR" "$UPDATE_LATEST" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
final_path, smoke_summary_path, run_id, run_root, out_dir, update_latest = sys.argv[1:]
smoke = json.loads(Path(smoke_summary_path).read_text(encoding="utf-8"))
summary = {
    "schema_version": "agent_modelica_multi_round_smoke3_final_run_summary_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_id": run_id,
    "run_root": run_root,
    "status": smoke.get("status"),
    "success_count": int(smoke.get("success_count") or 0),
    "total_tasks": int(smoke.get("total_tasks") or 0),
    "counts_by_library": smoke.get("counts_by_library") if isinstance(smoke.get("counts_by_library"), dict) else {},
    "paths": {"smoke_summary": smoke_summary_path},
}
Path(final_path).write_text(json.dumps(summary, indent=2), encoding="utf-8")
if str(update_latest) == "1":
    out_dir = Path(out_dir)
    (out_dir / "latest_run.json").write_text(json.dumps({"run_id": run_id, "run_root": run_root}, indent=2), encoding="utf-8")
PY
