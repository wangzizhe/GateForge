#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_LIVE_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_source_blind_multistep_live_evidence_v1}"
RUN_ID="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_RUN_ID:-$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).strftime("source_blind_multistep_%Y%m%dT%H%M%SZ"))
PY
)}"
RUN_ROOT="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_RUN_ROOT:-$OUT_DIR/runs/$RUN_ID}"
RESUME="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_RESUME:-0}"
STOP_AFTER_STAGE="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_STOP_AFTER_STAGE:-}"
UPDATE_LATEST="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_UPDATE_LATEST:-1}"

MANIFEST_PATH="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_MANIFEST:-assets_private/agent_modelica_source_blind_multistep_pack_v1/manifest.json}"
FAILURE_TYPES="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_FAILURE_TYPES:-stability_then_behavior,behavior_then_robustness,switch_then_recovery}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_SPLIT_SEED:-agent_modelica_source_blind_multistep_taskset_v1}"
REALISM_VERSION="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_REALISM_VERSION:-v3}"
MAX_ROUNDS="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_MAX_ROUNDS:-3}"
MAX_TIME_SEC="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_MAX_TIME_SEC:-300}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_LIVE_TIMEOUT_SEC:-300}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_LIVE_MAX_OUTPUT_CHARS:-2400}"
PLANNER_BACKEND="${GATEFORGE_AGENT_LIVE_PLANNER_BACKEND:-auto}"
OM_BACKEND="${GATEFORGE_AGENT_LIVE_OM_BACKEND:-openmodelica_docker}"
OM_DOCKER_IMAGE="${GATEFORGE_AGENT_LIVE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"

DEFAULT_LIVE_EXECUTOR_CMD="env GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE=source_blind python3 -m gateforge.agent_modelica_live_executor_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --source-library-path \"__SOURCE_LIBRARY_PATH__\" --source-package-name \"__SOURCE_PACKAGE_NAME__\" --source-library-model-path \"__SOURCE_LIBRARY_MODEL_PATH__\" --source-qualified-model-name \"__SOURCE_QUALIFIED_MODEL_NAME__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${PLANNER_BACKEND}\" --backend \"${OM_BACKEND}\" --docker-image \"${OM_DOCKER_IMAGE}\""
LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_LIVE_EXECUTOR_CMD:-$DEFAULT_LIVE_EXECUTOR_CMD}"
DETERMINISTIC_EXECUTOR_CMD="${GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_DETERMINISTIC_EXECUTOR_CMD:-env GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE=source_blind GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR=1 python3 -m gateforge.agent_modelica_live_executor_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --source-library-path \"__SOURCE_LIBRARY_PATH__\" --source-package-name \"__SOURCE_PACKAGE_NAME__\" --source-library-model-path \"__SOURCE_LIBRARY_MODEL_PATH__\" --source-qualified-model-name \"__SOURCE_QUALIFIED_MODEL_NAME__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${PLANNER_BACKEND}\" --backend \"${OM_BACKEND}\" --docker-image \"${OM_DOCKER_IMAGE}\"}"

CHALLENGE_DIR="$RUN_ROOT/challenge"
BASELINE_DIR="$RUN_ROOT/baseline_off_live"
DETERMINISTIC_DIR="$RUN_ROOT/deterministic_on_live"
RUN_MANIFEST_PATH="$RUN_ROOT/run_manifest.json"

mkdir -p "$OUT_DIR" "$OUT_DIR/runs" "$RUN_ROOT" "$CHALLENGE_DIR" "$BASELINE_DIR" "$DETERMINISTIC_DIR"

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
    "schema_version": "agent_modelica_source_blind_multistep_live_stage_status_v1",
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

python3 - "$RUN_MANIFEST_PATH" "$RUN_ID" "$RUN_ROOT" "$MANIFEST_PATH" "$REALISM_VERSION" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
path, run_id, run_root, manifest, realism_version = sys.argv[1:]
Path(path).write_text(json.dumps({
    "schema_version": "agent_modelica_source_blind_multistep_live_run_manifest_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_id": run_id,
    "run_root": run_root,
    "manifest_path": manifest,
    "source_mode": "source_blind",
    "realism_version": str(realism_version or "v3"),
}, indent=2), encoding="utf-8")
PY

run_stage "challenge" "$CHALLENGE_DIR/summary.json" \
  python3 -m gateforge.agent_modelica_source_blind_multistep_taskset_v1 \
    --manifest "$MANIFEST_PATH" \
    --out-dir "$CHALLENGE_DIR" \
    --failure-types "$FAILURE_TYPES" \
    --holdout-ratio "$HOLDOUT_RATIO" \
    --seed "$SPLIT_SEED" \
    --realism-version "$REALISM_VERSION"

if [ "$STOP_AFTER_STAGE" = "challenge" ]; then
  exit 0
fi

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

run_stage "source_blind_multistep_baseline_summary" "$RUN_ROOT/source_blind_multistep_baseline_summary.json" \
  python3 -m gateforge.agent_modelica_source_blind_multistep_baseline_summary_v1 \
    --challenge-summary "$CHALLENGE_DIR/summary.json" \
    --baseline-summary "$BASELINE_DIR/summary.json" \
    --baseline-results "$BASELINE_DIR/results.json" \
    --out "$RUN_ROOT/source_blind_multistep_baseline_summary.json"

if [ "$STOP_AFTER_STAGE" = "baseline_off_live" ] || [ "$STOP_AFTER_STAGE" = "source_blind_multistep_baseline_summary" ]; then
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

if [ "$STOP_AFTER_STAGE" = "deterministic_on_live" ]; then
  exit 0
fi

run_stage "source_blind_multistep_evidence" "$RUN_ROOT/evidence_summary.json" \
  python3 -m gateforge.agent_modelica_source_blind_multistep_evidence_v1 \
    --challenge-summary "$CHALLENGE_DIR/summary.json" \
    --baseline-summary "$RUN_ROOT/source_blind_multistep_baseline_summary.json" \
    --baseline-results "$BASELINE_DIR/results.json" \
    --deterministic-summary "$DETERMINISTIC_DIR/summary.json" \
    --deterministic-results "$DETERMINISTIC_DIR/results.json" \
    --out "$RUN_ROOT/evidence_summary.json" \
    --gate-out "$RUN_ROOT/gate_summary.json" \
    --decision-out "$RUN_ROOT/decision_summary.json"

python3 - <<'PY' "$OUT_DIR" "$RUN_ID" "$RUN_ROOT" "$UPDATE_LATEST"
import json
import sys
from pathlib import Path
out_dir, run_id, run_root, update_latest = sys.argv[1:]
if str(update_latest) == "1":
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "latest_run.json").write_text(json.dumps({"run_id": run_id, "run_root": run_root}, indent=2), encoding="utf-8")
PY
