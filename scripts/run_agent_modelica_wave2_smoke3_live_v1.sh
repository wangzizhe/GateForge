#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_WAVE2_SMOKE3_OUT_DIR:-artifacts/agent_modelica_wave2_smoke3_live_v1}"
RUN_ID="${GATEFORGE_AGENT_WAVE2_SMOKE3_RUN_ID:-$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).strftime("wave2_smoke3_%Y%m%dT%H%M%SZ"))
PY
)}"
RUN_ROOT="${GATEFORGE_AGENT_WAVE2_SMOKE3_RUN_ROOT:-$OUT_DIR/runs/$RUN_ID}"
UPDATE_LATEST="${GATEFORGE_AGENT_WAVE2_SMOKE3_UPDATE_LATEST:-1}"

MANIFEST_PATH="${GATEFORGE_AGENT_WAVE2_REALISM_MANIFEST:-assets_private/agent_modelica_wave2_realism_pack_v1/manifest.json}"
EXCLUDE_MODELS_JSON="${GATEFORGE_AGENT_WAVE2_REALISM_EXCLUDE_MODELS_JSON:-}"
SMOKE_TASK_IDS="${GATEFORGE_AGENT_WAVE2_SMOKE_TASK_IDS:-wave2_buildings_loads_overconstrained_system,wave2_ibpsa_loads_parameter_binding_error,wave2_transform_simplebattery_test_array_dimension_mismatch}"
FAILURE_TYPES="${GATEFORGE_AGENT_WAVE2_REALISM_FAILURE_TYPES:-overconstrained_system,parameter_binding_error,array_dimension_mismatch}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_WAVE2_REALISM_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_WAVE2_REALISM_SPLIT_SEED:-agent_modelica_wave2_realism_taskset_v1}"

MAX_ROUNDS="${GATEFORGE_AGENT_WAVE2_REALISM_MAX_ROUNDS:-2}"
MAX_TIME_SEC="${GATEFORGE_AGENT_WAVE2_REALISM_MAX_TIME_SEC:-300}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_WAVE2_REALISM_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_WAVE2_REALISM_LIVE_TIMEOUT_SEC:-300}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_WAVE2_REALISM_LIVE_MAX_OUTPUT_CHARS:-2400}"
PER_TASK_TIME_BUDGET_SEC="${GATEFORGE_AGENT_WAVE2_SMOKE3_PER_TASK_TIME_BUDGET_SEC:-300}"
MIN_TASKS_WITHIN_BUDGET="${GATEFORGE_AGENT_WAVE2_SMOKE3_MIN_TASKS_WITHIN_BUDGET:-2}"

PLANNER_BACKEND="${GATEFORGE_AGENT_LIVE_PLANNER_BACKEND:-gemini}"
OM_BACKEND="${GATEFORGE_AGENT_LIVE_OM_BACKEND:-openmodelica_docker}"
OM_DOCKER_IMAGE="${GATEFORGE_AGENT_LIVE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"
RUN_BACKEND_PREFLIGHT="${GATEFORGE_AGENT_WAVE2_REALISM_RUN_BACKEND_PREFLIGHT:-1}"

DEFAULT_LIVE_EXECUTOR_CMD="python3 -m gateforge.agent_modelica_live_executor_gemini_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --source-library-path \"__SOURCE_LIBRARY_PATH__\" --source-package-name \"__SOURCE_PACKAGE_NAME__\" --source-library-model-path \"__SOURCE_LIBRARY_MODEL_PATH__\" --source-qualified-model-name \"__SOURCE_QUALIFIED_MODEL_NAME__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${PLANNER_BACKEND}\" --backend \"${OM_BACKEND}\" --docker-image \"${OM_DOCKER_IMAGE}\""
LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_LIVE_EXECUTOR_CMD:-$DEFAULT_LIVE_EXECUTOR_CMD}"

CHALLENGE_DIR="$RUN_ROOT/challenge"
SMOKE_TASKSET_DIR="$RUN_ROOT/smoke_taskset"
BASELINE_DIR="$RUN_ROOT/baseline_off_live"
OM_LIBRARY_CACHE="${GATEFORGE_AGENT_OM_LIBRARY_CACHE:-$RUN_ROOT/.omlibrary_cache}"
BACKEND_PREFLIGHT_PATH="$RUN_ROOT/backend_preflight.json"
SMOKE_SUMMARY_PATH="$RUN_ROOT/smoke_summary.json"
FINAL_RUN_SUMMARY_PATH="$RUN_ROOT/final_run_summary.json"
RUN_MANIFEST_PATH="$RUN_ROOT/run_manifest.json"

mkdir -p "$OUT_DIR" "$OUT_DIR/runs" "$RUN_ROOT" "$CHALLENGE_DIR" "$SMOKE_TASKSET_DIR" "$BASELINE_DIR" "$OM_LIBRARY_CACHE"
OM_LIBRARY_CACHE="$(cd "$OM_LIBRARY_CACHE" && pwd)"
export GATEFORGE_OM_DOCKER_LIBRARY_CACHE="$OM_LIBRARY_CACHE"

write_json_file() {
  local out_path="$1"
  local payload_json="$2"
  python3 - "$out_path" "$payload_json" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
payload = json.loads(sys.argv[2])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY
}

stage_update() {
  local stage="$1"
  local status="$2"
  local summary_path="$3"
  python3 - "$RUN_ROOT" "$stage" "$status" "$summary_path" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
run_root, stage, status, summary_path = sys.argv[1:]
payload = {
    "schema_version": "agent_modelica_wave2_smoke3_stage_status_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "stage": stage,
    "status": status,
    "summary_path": summary_path,
    "complete": status in {"PASS", "FAIL", "NEEDS_REVIEW", "SKIPPED"},
}
path = Path(run_root) / "stages" / stage / "stage_status.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY
}

summary_status() {
  local summary_path="$1"
  python3 - "$summary_path" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
if not path.exists():
    print("FAIL")
    raise SystemExit(0)
payload = json.loads(path.read_text(encoding="utf-8"))
print(str(payload.get("status") or "FAIL").strip().upper() or "FAIL")
PY
}

run_stage() {
  local stage="$1"
  local summary_path="$2"
  shift 2
  stage_update "$stage" "RUNNING" "$summary_path"
  set +e
  "$@"
  local rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    stage_update "$stage" "FAIL" "$summary_path"
    exit "$rc"
  fi
  stage_update "$stage" "$(summary_status "$summary_path")" "$summary_path"
}

init_run_manifest() {
  python3 - "$RUN_MANIFEST_PATH" "$OUT_DIR" "$RUN_ROOT" "$RUN_ID" "$MANIFEST_PATH" "$SMOKE_TASK_IDS" "$MAX_ROUNDS" "$MAX_TIME_SEC" "$LIVE_TIMEOUT_SEC" "$PLANNER_BACKEND" "$OM_BACKEND" "$OM_DOCKER_IMAGE" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
(
    manifest_path,
    out_dir,
    run_root,
    run_id,
    source_manifest,
    smoke_task_ids,
    max_rounds,
    max_time_sec,
    live_timeout_sec,
    planner_backend,
    om_backend,
    om_docker_image,
) = sys.argv[1:]
payload = {
    "schema_version": "agent_modelica_wave2_smoke3_run_manifest_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_id": run_id,
    "out_dir": out_dir,
    "run_root": run_root,
    "source_manifest": source_manifest,
    "smoke_task_ids": [item.strip() for item in smoke_task_ids.split(",") if item.strip()],
    "runtime_config": {
        "max_rounds": int(max_rounds),
        "max_time_sec": int(max_time_sec),
        "live_timeout_sec": int(live_timeout_sec),
        "planner_backend": planner_backend,
        "om_backend": om_backend,
        "om_docker_image": om_docker_image,
    },
}
Path(manifest_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY
}

run_backend_preflight_stage() {
  if [ "$RUN_BACKEND_PREFLIGHT" != "1" ]; then
    write_json_file "$BACKEND_PREFLIGHT_PATH" '{"schema_version":"agent_modelica_wave2_backend_preflight_v1","status":"SKIPPED","reason":"backend_preflight_disabled"}'
    return 0
  fi
  python3 -m gateforge.smoke --backend "$OM_BACKEND" --out "$BACKEND_PREFLIGHT_PATH"
}

run_challenge_stage() {
  local args=(
    python3 -m gateforge.agent_modelica_wave2_realism_taskset_v1
    --manifest "$MANIFEST_PATH"
    --out-dir "$CHALLENGE_DIR"
    --failure-types "$FAILURE_TYPES"
    --holdout-ratio "$HOLDOUT_RATIO"
    --seed "$SPLIT_SEED"
  )
  if [ -n "$EXCLUDE_MODELS_JSON" ] && [ -f "$EXCLUDE_MODELS_JSON" ]; then
    args+=(--exclude-models-json "$EXCLUDE_MODELS_JSON")
  fi
  "${args[@]}"
}

run_smoke_taskset_stage() {
  python3 -m gateforge.agent_modelica_unknown_library_smoke_taskset_v1 \
    --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
    --task-ids-csv "$SMOKE_TASK_IDS" \
    --out-dir "$SMOKE_TASKSET_DIR"
}

run_baseline_off_live_stage() {
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
}

run_smoke_summary_stage() {
  python3 -m gateforge.agent_modelica_unknown_library_smoke3_summary_v1 \
    --taskset "$SMOKE_TASKSET_DIR/taskset_frozen.json" \
    --results "$BASELINE_DIR/results.json" \
    --records-jsonl "$BASELINE_DIR/records.jsonl" \
    --per-task-time-budget-sec "$PER_TASK_TIME_BUDGET_SEC" \
    --min-tasks-within-budget "$MIN_TASKS_WITHIN_BUDGET" \
    --out "$SMOKE_SUMMARY_PATH"
}

finalize_run() {
  python3 - "$FINAL_RUN_SUMMARY_PATH" "$SMOKE_SUMMARY_PATH" "$RUN_ID" "$RUN_ROOT" "$OUT_DIR" "$UPDATE_LATEST" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
final_path, smoke_summary_path, run_id, run_root, out_dir, update_latest = sys.argv[1:]
smoke = json.loads(Path(smoke_summary_path).read_text(encoding="utf-8")) if Path(smoke_summary_path).exists() else {}
summary = {
    "schema_version": "agent_modelica_wave2_smoke3_final_run_summary_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_id": run_id,
    "run_root": run_root,
    "status": str(smoke.get("status") or ""),
    "success_count": int(smoke.get("success_count") or 0),
    "total_tasks": int(smoke.get("total_tasks") or 0),
    "counts_by_library": smoke.get("counts_by_library") if isinstance(smoke.get("counts_by_library"), dict) else {},
    "paths": {"smoke_summary": smoke_summary_path},
}
final = Path(final_path)
final.parent.mkdir(parents=True, exist_ok=True)
final.write_text(json.dumps(summary, indent=2), encoding="utf-8")
if str(update_latest) != "1":
    raise SystemExit(0)
out_root = Path(out_dir)
(out_root / "latest_run.json").write_text(json.dumps({"run_id": run_id, "run_root": run_root, "status": summary["status"], "summary_path": str(final)}, indent=2), encoding="utf-8")
(out_root / "latest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
PY
}

init_run_manifest

run_stage "backend_preflight" "$BACKEND_PREFLIGHT_PATH" run_backend_preflight_stage
run_stage "challenge" "$CHALLENGE_DIR/summary.json" run_challenge_stage
run_stage "smoke_taskset" "$SMOKE_TASKSET_DIR/summary.json" run_smoke_taskset_stage
run_stage "baseline_off_live" "$BASELINE_DIR/summary.json" run_baseline_off_live_stage
run_stage "smoke_summary" "$SMOKE_SUMMARY_PATH" run_smoke_summary_stage

finalize_run
cat "$FINAL_RUN_SUMMARY_PATH"
