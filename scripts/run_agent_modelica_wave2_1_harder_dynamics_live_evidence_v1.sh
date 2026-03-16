#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_LIVE_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_wave2_1_harder_dynamics_live_evidence_v1}"
RUN_ID="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_RUN_ID:-$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).strftime("wave2_1_harder_dynamics_%Y%m%dT%H%M%SZ"))
PY
)}"
RUN_ROOT="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_RUN_ROOT:-$OUT_DIR/runs/$RUN_ID}"
RESUME="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_RESUME:-0}"
STOP_AFTER_STAGE="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_STOP_AFTER_STAGE:-}"

MANIFEST_PATH="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_MANIFEST:-assets_private/agent_modelica_wave2_1_harder_dynamics_pack_v1/manifest.json}"
EXCLUDE_MODELS_JSON="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_EXCLUDE_MODELS_JSON:-}"
REPAIR_MEMORY_PATH="${GATEFORGE_AGENT_REPAIR_MEMORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"
FAILURE_TYPES="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_FAILURE_TYPES:-solver_sensitive_simulate_failure,event_logic_error,semantic_drift_after_compile_pass}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_SPLIT_SEED:-agent_modelica_wave2_1_harder_dynamics_taskset_v1}"
MAX_ROUNDS="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_MAX_ROUNDS:-2}"
MAX_TIME_SEC="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_MAX_TIME_SEC:-180}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_LIVE_TIMEOUT_SEC:-180}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_LIVE_MAX_OUTPUT_CHARS:-2400}"
PLANNER_BACKEND="${GATEFORGE_AGENT_LIVE_PLANNER_BACKEND:-gemini}"
OM_BACKEND="${GATEFORGE_AGENT_LIVE_OM_BACKEND:-openmodelica_docker}"
OM_DOCKER_IMAGE="${GATEFORGE_AGENT_LIVE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"
RUN_BACKEND_PREFLIGHT="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_RUN_BACKEND_PREFLIGHT:-1}"
UPDATE_LATEST="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_UPDATE_LATEST:-1}"

DEFAULT_LIVE_EXECUTOR_CMD="python3 -m gateforge.agent_modelica_live_executor_gemini_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --source-library-path \"__SOURCE_LIBRARY_PATH__\" --source-package-name \"__SOURCE_PACKAGE_NAME__\" --source-library-model-path \"__SOURCE_LIBRARY_MODEL_PATH__\" --source-qualified-model-name \"__SOURCE_QUALIFIED_MODEL_NAME__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${PLANNER_BACKEND}\" --backend \"${OM_BACKEND}\" --docker-image \"${OM_DOCKER_IMAGE}\""
LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_LIVE_EXECUTOR_CMD:-$DEFAULT_LIVE_EXECUTOR_CMD}"
DETERMINISTIC_EXECUTOR_CMD="${GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_EXECUTOR_CMD:-env GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR=1 $LIVE_EXECUTOR_CMD}"

CHALLENGE_DIR="$RUN_ROOT/challenge"
CURATED_DIR="$RUN_ROOT/curated_retrieval"
BASELINE_DIR="$RUN_ROOT/baseline_off_live"
DETERMINISTIC_DIR="$RUN_ROOT/deterministic_on_live"
RETRIEVAL_DIR="$RUN_ROOT/retrieval_on_live"
RUN_MANIFEST_PATH="$RUN_ROOT/run_manifest.json"
FINAL_RUN_SUMMARY_PATH="$RUN_ROOT/final_run_summary.json"

mkdir -p "$OUT_DIR" "$OUT_DIR/runs" "$RUN_ROOT" "$CHALLENGE_DIR" "$CURATED_DIR" "$BASELINE_DIR" "$DETERMINISTIC_DIR" "$RETRIEVAL_DIR"

stage_update() {
  local stage="$1"
  local status="$2"
  local exit_code="$3"
  local summary_path="$4"
  python3 - "$RUN_ROOT" "$stage" "$status" "$exit_code" "$summary_path" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
run_root, stage, status, exit_code, summary_path = sys.argv[1:]
payload = {
    "schema_version": "agent_modelica_wave2_1_harder_dynamics_live_stage_status_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "stage": stage,
    "status": status,
    "exit_code": int(exit_code),
    "summary_path": summary_path,
    "complete": status in {"PASS", "FAIL", "NEEDS_REVIEW", "SKIPPED"},
}
path = Path(run_root) / "stages" / stage / "stage_status.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY
}

run_stage() {
  local stage="$1"
  local summary_path="$2"
  shift 2
  if [ "$RESUME" = "1" ] && [ -f "$summary_path" ]; then
    stage_update "$stage" "PASS" 0 "$summary_path"
    return 0
  fi
  stage_update "$stage" "RUNNING" 0 "$summary_path"
  set +e
  "$@"
  local rc=$?
  set -e
  local status="FAIL"
  if [ $rc -eq 0 ]; then
    status="PASS"
  fi
  stage_update "$stage" "$status" "$rc" "$summary_path"
  return $rc
}

python3 - "$RUN_MANIFEST_PATH" "$RUN_ID" "$RUN_ROOT" "$MANIFEST_PATH" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
path, run_id, run_root, manifest = sys.argv[1:]
Path(path).write_text(json.dumps({
    "schema_version": "agent_modelica_wave2_1_harder_dynamics_live_run_manifest_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_id": run_id,
    "run_root": run_root,
    "manifest_path": manifest,
}, indent=2), encoding="utf-8")
PY

if [ "$RUN_BACKEND_PREFLIGHT" = "1" ] && [ "$OM_BACKEND" = "openmodelica_docker" ]; then
  run_stage "backend_preflight" "$RUN_ROOT/backend_preflight.json" bash scripts/check_docker_backend.sh
fi

TASKSET_ARGS=(
  python3 -m gateforge.agent_modelica_wave2_1_harder_dynamics_taskset_v1
  --manifest "$MANIFEST_PATH"
  --out-dir "$CHALLENGE_DIR"
  --failure-types "$FAILURE_TYPES"
  --holdout-ratio "$HOLDOUT_RATIO"
  --seed "$SPLIT_SEED"
)
if [ -n "$EXCLUDE_MODELS_JSON" ] && [ -f "$EXCLUDE_MODELS_JSON" ]; then
  TASKSET_ARGS+=(--exclude-models-json "$EXCLUDE_MODELS_JSON")
fi
run_stage "challenge" "$CHALLENGE_DIR/summary.json" "${TASKSET_ARGS[@]}"
if [ "$STOP_AFTER_STAGE" = "challenge" ]; then
  echo "Stopped after stage: challenge"
  exit 0
fi

run_stage "curated_retrieval" "$CURATED_DIR/summary.json" \
  python3 -m gateforge.agent_modelica_wave2_1_curated_retrieval_v1 \
    --manifest "$MANIFEST_PATH" \
    --failure-types "$FAILURE_TYPES" \
    --history-out "$CURATED_DIR/history.json" \
    --out "$CURATED_DIR/summary.json"

python3 - "$REPAIR_MEMORY_PATH" "$CURATED_DIR/history.json" "$RUN_ROOT/merged_repair_history.json" <<'PY'
import json
import sys
from pathlib import Path
memory_path = Path(sys.argv[1])
curated_path = Path(sys.argv[2])
out_path = Path(sys.argv[3])
rows = []
if memory_path.exists():
    try:
        payload = json.loads(memory_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    source_rows = payload.get("rows") if isinstance(payload.get("rows"), list) else payload.get("records")
    if isinstance(source_rows, list):
        rows.extend([row for row in source_rows if isinstance(row, dict)])
curated = json.loads(curated_path.read_text(encoding="utf-8"))
rows.extend([row for row in (curated.get("rows") or []) if isinstance(row, dict)])
out_path.write_text(json.dumps({"schema_version": "agent_modelica_wave2_1_merged_history_v1", "rows": rows}, indent=2), encoding="utf-8")
PY

run_stage "baseline_off_live" "$BASELINE_DIR/summary.json" \
  python3 -m gateforge.agent_modelica_run_contract_v1 \
    --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
    --mode live \
    --max-rounds "$MAX_ROUNDS" \
    --max-time-sec "$MAX_TIME_SEC" \
    --runtime-threshold "$RUNTIME_THRESHOLD" \
    --live-executor-cmd "$LIVE_EXECUTOR_CMD" \
    --live-timeout-sec "$LIVE_TIMEOUT_SEC" \
    --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS" \
    --results-out "$BASELINE_DIR/results.json" \
    --out "$BASELINE_DIR/summary.json"

run_stage "wave2_1_baseline_summary" "$RUN_ROOT/wave2_1_baseline_summary.json" \
  python3 -m gateforge.agent_modelica_wave2_1_baseline_summary_v1 \
    --challenge-summary "$CHALLENGE_DIR/summary.json" \
    --baseline-summary "$BASELINE_DIR/summary.json" \
    --baseline-results "$BASELINE_DIR/results.json" \
    --out "$RUN_ROOT/wave2_1_baseline_summary.json"

if [ "$STOP_AFTER_STAGE" = "baseline_off_live" ] || [ "$STOP_AFTER_STAGE" = "wave2_1_baseline_summary" ]; then
  echo "Stopped after stage: baseline_off_live"
  exit 0
fi

run_stage "deterministic_on_live" "$DETERMINISTIC_DIR/summary.json" \
  python3 -m gateforge.agent_modelica_run_contract_v1 \
    --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
    --mode live \
    --max-rounds "$MAX_ROUNDS" \
    --max-time-sec "$MAX_TIME_SEC" \
    --runtime-threshold "$RUNTIME_THRESHOLD" \
    --live-executor-cmd "$DETERMINISTIC_EXECUTOR_CMD" \
    --live-timeout-sec "$LIVE_TIMEOUT_SEC" \
    --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS" \
    --results-out "$DETERMINISTIC_DIR/results.json" \
    --out "$DETERMINISTIC_DIR/summary.json"

run_stage "retrieval_on_live" "$RETRIEVAL_DIR/summary.json" \
  python3 -m gateforge.agent_modelica_run_contract_v1 \
    --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
    --mode live \
    --max-rounds "$MAX_ROUNDS" \
    --max-time-sec "$MAX_TIME_SEC" \
    --runtime-threshold "$RUNTIME_THRESHOLD" \
    --repair-history "$RUN_ROOT/merged_repair_history.json" \
    --live-executor-cmd "$DETERMINISTIC_EXECUTOR_CMD" \
    --live-timeout-sec "$LIVE_TIMEOUT_SEC" \
    --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS" \
    --results-out "$RETRIEVAL_DIR/results.json" \
    --out "$RETRIEVAL_DIR/summary.json"

run_stage "retrieval_summary" "$RUN_ROOT/retrieval_summary.json" \
  python3 -m gateforge.agent_modelica_unknown_library_retrieval_summary_v1 \
    --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
    --results "$RETRIEVAL_DIR/results.json" \
    --out "$RUN_ROOT/retrieval_summary.json"

run_stage "evidence" "$RUN_ROOT/decision_summary.json" \
  python3 -m gateforge.agent_modelica_wave2_1_evidence_v1 \
    --challenge-summary "$CHALLENGE_DIR/summary.json" \
    --baseline-summary "$BASELINE_DIR/summary.json" \
    --baseline-results "$BASELINE_DIR/results.json" \
    --deterministic-summary "$DETERMINISTIC_DIR/summary.json" \
    --deterministic-results "$DETERMINISTIC_DIR/results.json" \
    --retrieval-summary "$RETRIEVAL_DIR/summary.json" \
    --retrieval-results "$RETRIEVAL_DIR/results.json" \
    --retrieval-audit-summary "$RUN_ROOT/retrieval_summary.json" \
    --out "$RUN_ROOT/evidence_summary.json" \
    --gate-out "$RUN_ROOT/gate_summary.json" \
    --decision-out "$RUN_ROOT/decision_summary.json"

python3 - "$FINAL_RUN_SUMMARY_PATH" "$RUN_ID" "$RUN_ROOT" "$RUN_ROOT/decision_summary.json" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
final_path, run_id, run_root, decision_path = sys.argv[1:]
decision = json.loads(Path(decision_path).read_text(encoding="utf-8"))
payload = {
    "schema_version": "agent_modelica_wave2_1_harder_dynamics_live_final_run_summary_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_id": run_id,
    "run_root": run_root,
    "status": decision.get("status"),
    "decision": decision.get("decision"),
    "primary_reason": decision.get("primary_reason"),
    "retrieval_uplift_status": decision.get("retrieval_uplift_status"),
    "baseline_saturation_status": decision.get("baseline_saturation_status"),
}
Path(final_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

if [ "$UPDATE_LATEST" = "1" ]; then
  python3 - "$OUT_DIR" "$RUN_ID" "$RUN_ROOT" <<'PY'
import json
import sys
from pathlib import Path
out_dir, run_id, run_root = sys.argv[1:]
Path(out_dir, "latest_run.json").write_text(json.dumps({"run_id": run_id, "run_root": run_root}, indent=2), encoding="utf-8")
Path(out_dir, "latest_summary.json").write_text(json.dumps({"run_id": run_id, "run_root": run_root}, indent=2), encoding="utf-8")
Path(out_dir, "latest_decision_summary.json").write_text((Path(run_root) / "decision_summary.json").read_text(encoding="utf-8"), encoding="utf-8")
PY
fi

cat "$FINAL_RUN_SUMMARY_PATH"
