#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L4_UPLIFT_OUT_DIR:-artifacts/agent_modelica_l4_uplift_evidence_v0}"
CHALLENGE_OUT="${GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_OUT_DIR:-$OUT_DIR/challenge}"
MAIN_SWEEP_OUT="${GATEFORGE_AGENT_L4_UPLIFT_MAIN_SWEEP_OUT_DIR:-$OUT_DIR/main_sweep}"
NIGHT_SWEEP_OUT="${GATEFORGE_AGENT_L4_UPLIFT_NIGHT_SWEEP_OUT_DIR:-$OUT_DIR/night_sweep}"
MAIN_L5_OUT="${GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_OUT_DIR:-$OUT_DIR/main_l5}"
NIGHT_L5_OUT="${GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_OUT_DIR:-$OUT_DIR/night_l5}"
RUN_ROOT="${GATEFORGE_AGENT_L4_UPLIFT_RUN_ROOT:-}"

BASE_TASKSET="${GATEFORGE_AGENT_L4_UPLIFT_BASE_TASKSET:-assets_private/agent_modelica_l2_freeze_pack_v0/taskset_frozen.json}"
SCALES="${GATEFORGE_AGENT_L4_UPLIFT_SCALES:-small,medium}"
PROFILES="${GATEFORGE_AGENT_L4_UPLIFT_PROFILES:-score_v1,score_v1a,score_v1b,score_v1c}"
REALISM_MODE="${GATEFORGE_AGENT_L4_UPLIFT_REALISM_MODE:-full}"
ENABLE_NIGHT="${GATEFORGE_AGENT_L4_UPLIFT_ENABLE_NIGHT:-1}"

BACKEND="${GATEFORGE_AGENT_L4_UPLIFT_BACKEND:-openmodelica_docker}"
OM_DOCKER_IMAGE="${GATEFORGE_AGENT_L4_UPLIFT_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"
GLOBAL_LIVE_PLANNER_BACKEND="${GATEFORGE_AGENT_LIVE_PLANNER_BACKEND:-${LLM_PROVIDER:-}}"
MAIN_PLANNER_BACKEND="${GATEFORGE_AGENT_L4_UPLIFT_MAIN_PLANNER_BACKEND:-${GLOBAL_LIVE_PLANNER_BACKEND:-rule}}"
NIGHT_PLANNER_BACKEND="${GATEFORGE_AGENT_L4_UPLIFT_NIGHT_PLANNER_BACKEND:-${GLOBAL_LIVE_PLANNER_BACKEND:-gemini}}"
MAIN_GATE_MODE="${GATEFORGE_AGENT_L4_UPLIFT_MAIN_GATE_MODE:-strict}"
NIGHT_GATE_MODE="${GATEFORGE_AGENT_L4_UPLIFT_NIGHT_GATE_MODE:-observe}"
CHALLENGE_PLANNER_BACKEND="${GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_PLANNER_BACKEND:-${GLOBAL_LIVE_PLANNER_BACKEND:-gemini}}"
CHALLENGE_LLM_MODEL="${GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LLM_MODEL:-${LLM_MODEL:-${GATEFORGE_GEMINI_MODEL:-}}}"

MAX_ROUNDS="${GATEFORGE_AGENT_L4_UPLIFT_MAX_ROUNDS:-2}"
MAX_TIME_SEC="${GATEFORGE_AGENT_L4_UPLIFT_MAX_TIME_SEC:-180}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_L4_UPLIFT_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_L4_UPLIFT_LIVE_TIMEOUT_SEC:-90}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_L4_UPLIFT_LIVE_MAX_OUTPUT_CHARS:-2400}"

L4_MAX_ROUNDS="${GATEFORGE_AGENT_L4_UPLIFT_L4_MAX_ROUNDS:-3}"
L4_POLICY_BACKEND="${GATEFORGE_AGENT_L4_UPLIFT_L4_POLICY_BACKEND:-rule}"
L4_LLM_FALLBACK_THRESHOLD="${GATEFORGE_AGENT_L4_UPLIFT_L4_LLM_FALLBACK_THRESHOLD:-2}"
L4_MAX_ACTIONS_PER_ROUND="${GATEFORGE_AGENT_L4_UPLIFT_L4_MAX_ACTIONS_PER_ROUND:-3}"

TARGET_MIN_OFF_SUCCESS_PCT="${GATEFORGE_AGENT_L4_UPLIFT_TARGET_MIN_OFF_SUCCESS_PCT:-60}"
PER_FAILURE_TYPE_CAP="${GATEFORGE_AGENT_L4_UPLIFT_PER_FAILURE_TYPE_CAP:-6}"
FAILURE_TYPES="${GATEFORGE_AGENT_L4_UPLIFT_FAILURE_TYPES:-model_check_error,simulate_error,semantic_regression}"
REQUIRED_CATEGORIES="${GATEFORGE_AGENT_L4_UPLIFT_REQUIRED_CATEGORIES:-}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_L4_UPLIFT_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_L4_UPLIFT_SPLIT_SEED:-agent_modelica_l4_challenge_v0}"
PACK_ID="${GATEFORGE_AGENT_L4_UPLIFT_PACK_ID:-}"
PACK_VERSION="${GATEFORGE_AGENT_L4_UPLIFT_PACK_VERSION:-}"
PACK_TRACK="${GATEFORGE_AGENT_L4_UPLIFT_PACK_TRACK:-}"
ACCEPTANCE_SCOPE="${GATEFORGE_AGENT_L4_UPLIFT_ACCEPTANCE_SCOPE:-}"
CONTINUE_ON_WEAK_BASELINE="${GATEFORGE_AGENT_L4_UPLIFT_CONTINUE_ON_WEAK_BASELINE:-0}"

MIN_DELTA_SUCCESS_PP="${GATEFORGE_AGENT_L4_UPLIFT_MIN_DELTA_SUCCESS_PP:-5}"
ABSOLUTE_SUCCESS_TARGET_PCT="${GATEFORGE_AGENT_L4_UPLIFT_ABSOLUTE_SUCCESS_TARGET_PCT:-85}"
NON_REGRESSION_TOLERANCE_PP="${GATEFORGE_AGENT_L4_UPLIFT_NON_REGRESSION_TOLERANCE_PP:-0}"
MAX_REGRESSION_WORSEN_PP="${GATEFORGE_AGENT_L4_UPLIFT_MAX_REGRESSION_WORSEN_PP:-2}"
MAX_PHYSICS_WORSEN_PP="${GATEFORGE_AGENT_L4_UPLIFT_MAX_PHYSICS_WORSEN_PP:-2}"
L5_INFRA_MUST_EQUAL="${GATEFORGE_AGENT_L4_UPLIFT_L5_INFRA_MUST_EQUAL:-0}"
L5_MIN_L3_PARSE_PCT="${GATEFORGE_AGENT_L4_UPLIFT_L5_MIN_L3_PARSE_PCT:-95}"
L5_MIN_L3_TYPE_PCT="${GATEFORGE_AGENT_L4_UPLIFT_L5_MIN_L3_TYPE_PCT:-70}"
L5_MIN_L3_STAGE_PCT="${GATEFORGE_AGENT_L4_UPLIFT_L5_MIN_L3_STAGE_PCT:-70}"

L5_LEDGER_PATH="${GATEFORGE_AGENT_L4_UPLIFT_L5_LEDGER_PATH:-$OUT_DIR/private/l5_eval_ledger_v1.jsonl}"
ENFORCE_PROMOTE="${GATEFORGE_AGENT_L4_UPLIFT_ENFORCE_PROMOTE:-0}"
TARGET_MAX_OFF_SUCCESS_PCT="${GATEFORGE_AGENT_L4_UPLIFT_TARGET_MAX_OFF_SUCCESS_PCT:-$(python3 - "$MIN_DELTA_SUCCESS_PP" <<'PY'
import sys
delta = float(sys.argv[1] or 5.0)
print(max(0.0, 100.0 - delta))
PY
)}"

DEFAULT_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_LIVE_EXECUTOR_CMD:-}"
CHALLENGE_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LIVE_EXECUTOR_CMD:-$DEFAULT_EXECUTOR_CMD}"
MAIN_SWEEP_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_MAIN_SWEEP_LIVE_EXECUTOR_CMD:-$DEFAULT_EXECUTOR_CMD}"
NIGHT_SWEEP_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_NIGHT_SWEEP_LIVE_EXECUTOR_CMD:-$DEFAULT_EXECUTOR_CMD}"
MAIN_L5_L3_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L3_LIVE_EXECUTOR_CMD:-$DEFAULT_EXECUTOR_CMD}"
MAIN_L5_L4_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L4_LIVE_EXECUTOR_CMD:-$DEFAULT_EXECUTOR_CMD}"
NIGHT_L5_L3_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L3_LIVE_EXECUTOR_CMD:-$DEFAULT_EXECUTOR_CMD}"
NIGHT_L5_L4_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L4_LIVE_EXECUTOR_CMD:-$DEFAULT_EXECUTOR_CMD}"
LIVE_LEDGER_PATH="${GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH:-$OUT_DIR/private/live_request_ledger.json}"

if [ ! -f "$BASE_TASKSET" ]; then
  echo "Missing base taskset: $BASE_TASKSET" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

write_stage_status() {
  local stage="$1"
  local status="$2"
  local exit_code="${3:-0}"
  local summary_path="${4:-}"
  local details_json="${5:-{}}"
  if [ -z "$RUN_ROOT" ]; then
    return 0
  fi
  python3 -m gateforge.agent_modelica_realism_run_lifecycle_v1 stage-update \
    --run-root "$RUN_ROOT" \
    --stage "$stage" \
    --status "$status" \
    --exit-code "$exit_code" \
    --summary-path "$summary_path" \
    --details-json "$details_json" >/dev/null
}

summary_status() {
  python3 - "$1" "$2" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
rc = int(sys.argv[2] or 0)
if not path.exists():
    print("FAIL" if rc != 0 else "NEEDS_REVIEW")
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("FAIL" if rc != 0 else "NEEDS_REVIEW")
    raise SystemExit(0)
if isinstance(payload, dict):
    status = str(payload.get("status") or "").strip()
    if status:
        print(status)
        raise SystemExit(0)
print("FAIL" if rc != 0 else "NEEDS_REVIEW")
PY
}

run_challenge() {
  if [ -n "$CHALLENGE_EXECUTOR_CMD" ]; then
    GATEFORGE_AGENT_L4_CHALLENGE_OUT_DIR="$CHALLENGE_OUT" \
    GATEFORGE_AGENT_L4_CHALLENGE_BASE_TASKSET="$BASE_TASKSET" \
    GATEFORGE_AGENT_L4_CHALLENGE_SCALES="$SCALES" \
    GATEFORGE_AGENT_L4_CHALLENGE_FAILURE_TYPES="$FAILURE_TYPES" \
    GATEFORGE_AGENT_L4_CHALLENGE_REQUIRED_CATEGORIES="$REQUIRED_CATEGORIES" \
    GATEFORGE_AGENT_L4_CHALLENGE_PER_FAILURE_TYPE_CAP="$PER_FAILURE_TYPE_CAP" \
    GATEFORGE_AGENT_L4_CHALLENGE_HOLDOUT_RATIO="$HOLDOUT_RATIO" \
    GATEFORGE_AGENT_L4_CHALLENGE_SPLIT_SEED="$SPLIT_SEED" \
    GATEFORGE_AGENT_L4_CHALLENGE_PACK_ID="$PACK_ID" \
    GATEFORGE_AGENT_L4_CHALLENGE_PACK_VERSION="$PACK_VERSION" \
    GATEFORGE_AGENT_L4_CHALLENGE_PACK_TRACK="$PACK_TRACK" \
    GATEFORGE_AGENT_L4_CHALLENGE_ACCEPTANCE_SCOPE="$ACCEPTANCE_SCOPE" \
    GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MIN_OFF_SUCCESS_PCT="$TARGET_MIN_OFF_SUCCESS_PCT" \
    GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MAX_OFF_SUCCESS_PCT="$TARGET_MAX_OFF_SUCCESS_PCT" \
    GATEFORGE_AGENT_L4_CHALLENGE_ENFORCE_BASELINE_RANGE="0" \
    GATEFORGE_AGENT_L4_CHALLENGE_PLANNER_BACKEND="$CHALLENGE_PLANNER_BACKEND" \
    GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_PLANNER_BACKEND="$CHALLENGE_PLANNER_BACKEND" \
    GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_LLM_MODEL="$CHALLENGE_LLM_MODEL" \
    GATEFORGE_AGENT_L4_CHALLENGE_BACKEND="$BACKEND" \
    GATEFORGE_AGENT_L4_CHALLENGE_OM_DOCKER_IMAGE="$OM_DOCKER_IMAGE" \
    GATEFORGE_AGENT_L4_CHALLENGE_MAX_ROUNDS="$MAX_ROUNDS" \
    GATEFORGE_AGENT_L4_CHALLENGE_MAX_TIME_SEC="$MAX_TIME_SEC" \
    GATEFORGE_AGENT_L4_CHALLENGE_RUNTIME_THRESHOLD="$RUNTIME_THRESHOLD" \
    GATEFORGE_AGENT_L4_CHALLENGE_LIVE_TIMEOUT_SEC="$LIVE_TIMEOUT_SEC" \
    GATEFORGE_AGENT_L4_CHALLENGE_LIVE_MAX_OUTPUT_CHARS="$LIVE_MAX_OUTPUT_CHARS" \
    GATEFORGE_AGENT_L4_CHALLENGE_LIVE_EXECUTOR_CMD="$CHALLENGE_EXECUTOR_CMD" \
    GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH="$LIVE_LEDGER_PATH" \
    GATEFORGE_AGENT_LIVE_REQUEST_STAGE="challenge" \
    bash scripts/run_agent_modelica_l4_challenge_pack_v0.sh
  else
    GATEFORGE_AGENT_L4_CHALLENGE_OUT_DIR="$CHALLENGE_OUT" \
    GATEFORGE_AGENT_L4_CHALLENGE_BASE_TASKSET="$BASE_TASKSET" \
    GATEFORGE_AGENT_L4_CHALLENGE_SCALES="$SCALES" \
    GATEFORGE_AGENT_L4_CHALLENGE_FAILURE_TYPES="$FAILURE_TYPES" \
    GATEFORGE_AGENT_L4_CHALLENGE_REQUIRED_CATEGORIES="$REQUIRED_CATEGORIES" \
    GATEFORGE_AGENT_L4_CHALLENGE_PER_FAILURE_TYPE_CAP="$PER_FAILURE_TYPE_CAP" \
    GATEFORGE_AGENT_L4_CHALLENGE_HOLDOUT_RATIO="$HOLDOUT_RATIO" \
    GATEFORGE_AGENT_L4_CHALLENGE_SPLIT_SEED="$SPLIT_SEED" \
    GATEFORGE_AGENT_L4_CHALLENGE_PACK_ID="$PACK_ID" \
    GATEFORGE_AGENT_L4_CHALLENGE_PACK_VERSION="$PACK_VERSION" \
    GATEFORGE_AGENT_L4_CHALLENGE_PACK_TRACK="$PACK_TRACK" \
    GATEFORGE_AGENT_L4_CHALLENGE_ACCEPTANCE_SCOPE="$ACCEPTANCE_SCOPE" \
    GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MIN_OFF_SUCCESS_PCT="$TARGET_MIN_OFF_SUCCESS_PCT" \
    GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MAX_OFF_SUCCESS_PCT="$TARGET_MAX_OFF_SUCCESS_PCT" \
    GATEFORGE_AGENT_L4_CHALLENGE_ENFORCE_BASELINE_RANGE="0" \
    GATEFORGE_AGENT_L4_CHALLENGE_PLANNER_BACKEND="$CHALLENGE_PLANNER_BACKEND" \
    GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_PLANNER_BACKEND="$CHALLENGE_PLANNER_BACKEND" \
    GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_LLM_MODEL="$CHALLENGE_LLM_MODEL" \
    GATEFORGE_AGENT_L4_CHALLENGE_BACKEND="$BACKEND" \
    GATEFORGE_AGENT_L4_CHALLENGE_OM_DOCKER_IMAGE="$OM_DOCKER_IMAGE" \
    GATEFORGE_AGENT_L4_CHALLENGE_MAX_ROUNDS="$MAX_ROUNDS" \
    GATEFORGE_AGENT_L4_CHALLENGE_MAX_TIME_SEC="$MAX_TIME_SEC" \
    GATEFORGE_AGENT_L4_CHALLENGE_RUNTIME_THRESHOLD="$RUNTIME_THRESHOLD" \
    GATEFORGE_AGENT_L4_CHALLENGE_LIVE_TIMEOUT_SEC="$LIVE_TIMEOUT_SEC" \
    GATEFORGE_AGENT_L4_CHALLENGE_LIVE_MAX_OUTPUT_CHARS="$LIVE_MAX_OUTPUT_CHARS" \
    GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH="$LIVE_LEDGER_PATH" \
    GATEFORGE_AGENT_LIVE_REQUEST_STAGE="challenge" \
    bash scripts/run_agent_modelica_l4_challenge_pack_v0.sh
  fi
}

run_sweep() {
  local planner_backend="$1"
  local out_dir="$2"
  local executor_cmd="$3"
  if [ -n "$executor_cmd" ]; then
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_OUT_DIR="$out_dir" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_TASKSET="$CHALLENGE_OUT/taskset_frozen.json" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_SCALES="$SCALES" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_PROFILES="$PROFILES" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_PLANNER_BACKEND="$planner_backend" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_BACKEND="$BACKEND" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_OM_DOCKER_IMAGE="$OM_DOCKER_IMAGE" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_ROUNDS="$MAX_ROUNDS" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_TIME_SEC="$MAX_TIME_SEC" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_RUNTIME_THRESHOLD="$RUNTIME_THRESHOLD" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_TIMEOUT_SEC="$LIVE_TIMEOUT_SEC" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_MAX_OUTPUT_CHARS="$LIVE_MAX_OUTPUT_CHARS" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_EXECUTOR_CMD="$executor_cmd" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_MAX_ROUNDS="$L4_MAX_ROUNDS" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_POLICY_BACKEND="$L4_POLICY_BACKEND" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_LLM_FALLBACK_THRESHOLD="$L4_LLM_FALLBACK_THRESHOLD" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_MAX_ACTIONS_PER_ROUND="$L4_MAX_ACTIONS_PER_ROUND" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_MIN_SUCCESS_DELTA_PP="$MIN_DELTA_SUCCESS_PP" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_REGRESSION_WORSEN_PP="$MAX_REGRESSION_WORSEN_PP" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_PHYSICS_WORSEN_PP="$MAX_PHYSICS_WORSEN_PP" \
    GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH="$LIVE_LEDGER_PATH" \
    GATEFORGE_AGENT_LIVE_REQUEST_STAGE="$(basename "$out_dir")" \
    bash scripts/run_agent_modelica_l4_profile_sweep_v0.sh
  else
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_OUT_DIR="$out_dir" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_TASKSET="$CHALLENGE_OUT/taskset_frozen.json" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_SCALES="$SCALES" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_PROFILES="$PROFILES" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_PLANNER_BACKEND="$planner_backend" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_BACKEND="$BACKEND" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_OM_DOCKER_IMAGE="$OM_DOCKER_IMAGE" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_ROUNDS="$MAX_ROUNDS" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_TIME_SEC="$MAX_TIME_SEC" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_RUNTIME_THRESHOLD="$RUNTIME_THRESHOLD" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_TIMEOUT_SEC="$LIVE_TIMEOUT_SEC" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_MAX_OUTPUT_CHARS="$LIVE_MAX_OUTPUT_CHARS" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_MAX_ROUNDS="$L4_MAX_ROUNDS" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_POLICY_BACKEND="$L4_POLICY_BACKEND" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_LLM_FALLBACK_THRESHOLD="$L4_LLM_FALLBACK_THRESHOLD" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_MAX_ACTIONS_PER_ROUND="$L4_MAX_ACTIONS_PER_ROUND" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_MIN_SUCCESS_DELTA_PP="$MIN_DELTA_SUCCESS_PP" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_REGRESSION_WORSEN_PP="$MAX_REGRESSION_WORSEN_PP" \
    GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_PHYSICS_WORSEN_PP="$MAX_PHYSICS_WORSEN_PP" \
    GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH="$LIVE_LEDGER_PATH" \
    GATEFORGE_AGENT_LIVE_REQUEST_STAGE="$(basename "$out_dir")" \
    bash scripts/run_agent_modelica_l4_profile_sweep_v0.sh
  fi
}

run_l5_eval() {
  local planner_backend="$1"
  local gate_mode="$2"
  local out_dir="$3"
  local policy_profile="$4"
  local l3_executor_cmd="$5"
  local l4_executor_cmd="$6"
  if [ -n "$l3_executor_cmd" ] && [ -n "$l4_executor_cmd" ]; then
    GATEFORGE_AGENT_L5_EVAL_TASKSET="$CHALLENGE_OUT/taskset_frozen.json" \
    GATEFORGE_AGENT_L5_EVAL_SCALES="$SCALES" \
    GATEFORGE_AGENT_L5_EVAL_OUT_DIR="$out_dir" \
    GATEFORGE_AGENT_L5_LEDGER_PATH="$L5_LEDGER_PATH" \
    GATEFORGE_AGENT_L5_GATE_MODE="$gate_mode" \
    GATEFORGE_AGENT_L5_EVAL_PLANNER_BACKEND="$planner_backend" \
    GATEFORGE_AGENT_L5_EVAL_BACKEND="$BACKEND" \
    GATEFORGE_AGENT_L5_EVAL_OM_DOCKER_IMAGE="$OM_DOCKER_IMAGE" \
    GATEFORGE_AGENT_L5_EVAL_MAX_ROUNDS="$MAX_ROUNDS" \
    GATEFORGE_AGENT_L5_EVAL_MAX_TIME_SEC="$MAX_TIME_SEC" \
    GATEFORGE_AGENT_L5_EVAL_RUNTIME_THRESHOLD="$RUNTIME_THRESHOLD" \
    GATEFORGE_AGENT_L5_EVAL_LIVE_TIMEOUT_SEC="$LIVE_TIMEOUT_SEC" \
    GATEFORGE_AGENT_L5_EVAL_LIVE_MAX_OUTPUT_CHARS="$LIVE_MAX_OUTPUT_CHARS" \
    GATEFORGE_AGENT_L5_ACCEPTANCE_MODE="$ACCEPTANCE_MODE" \
    GATEFORGE_AGENT_L5_ABSOLUTE_SUCCESS_TARGET_PCT="$ABSOLUTE_SUCCESS_TARGET_PCT" \
    GATEFORGE_AGENT_L5_NON_REGRESSION_TOLERANCE_PP="$NON_REGRESSION_TOLERANCE_PP" \
    GATEFORGE_AGENT_L5_BASELINE_REFERENCE_SUCCESS_PCT="$CHALLENGE_BASELINE_OFF_SUCCESS_PCT" \
    GATEFORGE_AGENT_L4_POLICY_PROFILE="$policy_profile" \
    GATEFORGE_AGENT_L4_POLICY_BACKEND="$L4_POLICY_BACKEND" \
    GATEFORGE_AGENT_L4_LLM_FALLBACK_THRESHOLD="$L4_LLM_FALLBACK_THRESHOLD" \
    GATEFORGE_AGENT_L4_MAX_ROUNDS="$L4_MAX_ROUNDS" \
    GATEFORGE_AGENT_L4_MAX_ACTIONS_PER_ROUND="$L4_MAX_ACTIONS_PER_ROUND" \
    GATEFORGE_AGENT_L5_MIN_DELTA_SUCCESS_PP="$MIN_DELTA_SUCCESS_PP" \
    GATEFORGE_AGENT_L5_MAX_REGRESSION_WORSEN_PP="$MAX_REGRESSION_WORSEN_PP" \
    GATEFORGE_AGENT_L5_MAX_PHYSICS_WORSEN_PP="$MAX_PHYSICS_WORSEN_PP" \
    GATEFORGE_AGENT_L5_INFRA_FAILURE_MUST_EQUAL="$L5_INFRA_MUST_EQUAL" \
    GATEFORGE_AGENT_L5_MIN_L3_PARSE_PCT="$L5_MIN_L3_PARSE_PCT" \
    GATEFORGE_AGENT_L5_MIN_L3_TYPE_PCT="$L5_MIN_L3_TYPE_PCT" \
    GATEFORGE_AGENT_L5_MIN_L3_STAGE_PCT="$L5_MIN_L3_STAGE_PCT" \
    GATEFORGE_AGENT_L5_EVAL_L3_LIVE_EXECUTOR_CMD="$l3_executor_cmd" \
    GATEFORGE_AGENT_L5_EVAL_L4_LIVE_EXECUTOR_CMD="$l4_executor_cmd" \
    GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH="$LIVE_LEDGER_PATH" \
    GATEFORGE_AGENT_LIVE_REQUEST_STAGE="$(basename "$out_dir")" \
    bash scripts/run_agent_modelica_l5_eval_v1.sh
  else
    GATEFORGE_AGENT_L5_EVAL_TASKSET="$CHALLENGE_OUT/taskset_frozen.json" \
    GATEFORGE_AGENT_L5_EVAL_SCALES="$SCALES" \
    GATEFORGE_AGENT_L5_EVAL_OUT_DIR="$out_dir" \
    GATEFORGE_AGENT_L5_LEDGER_PATH="$L5_LEDGER_PATH" \
    GATEFORGE_AGENT_L5_GATE_MODE="$gate_mode" \
    GATEFORGE_AGENT_L5_EVAL_PLANNER_BACKEND="$planner_backend" \
    GATEFORGE_AGENT_L5_EVAL_BACKEND="$BACKEND" \
    GATEFORGE_AGENT_L5_EVAL_OM_DOCKER_IMAGE="$OM_DOCKER_IMAGE" \
    GATEFORGE_AGENT_L5_EVAL_MAX_ROUNDS="$MAX_ROUNDS" \
    GATEFORGE_AGENT_L5_EVAL_MAX_TIME_SEC="$MAX_TIME_SEC" \
    GATEFORGE_AGENT_L5_EVAL_RUNTIME_THRESHOLD="$RUNTIME_THRESHOLD" \
    GATEFORGE_AGENT_L5_EVAL_LIVE_TIMEOUT_SEC="$LIVE_TIMEOUT_SEC" \
    GATEFORGE_AGENT_L5_EVAL_LIVE_MAX_OUTPUT_CHARS="$LIVE_MAX_OUTPUT_CHARS" \
    GATEFORGE_AGENT_L5_ACCEPTANCE_MODE="$ACCEPTANCE_MODE" \
    GATEFORGE_AGENT_L5_ABSOLUTE_SUCCESS_TARGET_PCT="$ABSOLUTE_SUCCESS_TARGET_PCT" \
    GATEFORGE_AGENT_L5_NON_REGRESSION_TOLERANCE_PP="$NON_REGRESSION_TOLERANCE_PP" \
    GATEFORGE_AGENT_L5_BASELINE_REFERENCE_SUCCESS_PCT="$CHALLENGE_BASELINE_OFF_SUCCESS_PCT" \
    GATEFORGE_AGENT_L4_POLICY_PROFILE="$policy_profile" \
    GATEFORGE_AGENT_L4_POLICY_BACKEND="$L4_POLICY_BACKEND" \
    GATEFORGE_AGENT_L4_LLM_FALLBACK_THRESHOLD="$L4_LLM_FALLBACK_THRESHOLD" \
    GATEFORGE_AGENT_L4_MAX_ROUNDS="$L4_MAX_ROUNDS" \
    GATEFORGE_AGENT_L4_MAX_ACTIONS_PER_ROUND="$L4_MAX_ACTIONS_PER_ROUND" \
    GATEFORGE_AGENT_L5_MIN_DELTA_SUCCESS_PP="$MIN_DELTA_SUCCESS_PP" \
    GATEFORGE_AGENT_L5_MAX_REGRESSION_WORSEN_PP="$MAX_REGRESSION_WORSEN_PP" \
    GATEFORGE_AGENT_L5_MAX_PHYSICS_WORSEN_PP="$MAX_PHYSICS_WORSEN_PP" \
    GATEFORGE_AGENT_L5_INFRA_FAILURE_MUST_EQUAL="$L5_INFRA_MUST_EQUAL" \
    GATEFORGE_AGENT_L5_MIN_L3_PARSE_PCT="$L5_MIN_L3_PARSE_PCT" \
    GATEFORGE_AGENT_L5_MIN_L3_TYPE_PCT="$L5_MIN_L3_TYPE_PCT" \
    GATEFORGE_AGENT_L5_MIN_L3_STAGE_PCT="$L5_MIN_L3_STAGE_PCT" \
    GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH="$LIVE_LEDGER_PATH" \
    GATEFORGE_AGENT_LIVE_REQUEST_STAGE="$(basename "$out_dir")" \
    bash scripts/run_agent_modelica_l5_eval_v1.sh
  fi
}

set +e
write_stage_status "challenge" "RUNNING" 0 "$CHALLENGE_OUT/frozen_summary.json"
run_challenge
CHALLENGE_RC=$?
set -e

CHALLENGE_SUMMARY="$CHALLENGE_OUT/frozen_summary.json"
CHALLENGE_TASKSET="$CHALLENGE_OUT/taskset_frozen.json"
if [ ! -f "$CHALLENGE_SUMMARY" ] || [ ! -f "$CHALLENGE_TASKSET" ]; then
  write_stage_status "challenge" "FAIL" "$CHALLENGE_RC" "$CHALLENGE_SUMMARY"
  echo "Missing challenge artifacts under $CHALLENGE_OUT" >&2
  exit 1
fi
write_stage_status "challenge" "$(summary_status "$CHALLENGE_SUMMARY" "$CHALLENGE_RC")" "$CHALLENGE_RC" "$CHALLENGE_SUMMARY"
CHALLENGE_BASELINE_OFF_SUCCESS_PCT="$(python3 - "$CHALLENGE_SUMMARY" <<'PY'
import json
import sys
from pathlib import Path
summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = summary.get("baseline_off_success_at_k_pct")
print("" if value is None else str(value))
PY
)"

BASELINE_STATE="$(python3 - "$CHALLENGE_SUMMARY" "$MIN_DELTA_SUCCESS_PP" <<'PY'
import json
import sys
from pathlib import Path
summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
min_delta_success_pp = float(sys.argv[2] or 5.0)
meets = summary.get("baseline_meets_minimum")
if meets is None:
    meets = summary.get("baseline_in_target_range")
has_headroom = summary.get("baseline_has_headroom")
if has_headroom is None:
    baseline = float(summary.get("baseline_off_success_at_k_pct") or 0.0)
    has_headroom = baseline <= max(0.0, 100.0 - min_delta_success_pp)
meets = bool(meets is True)
has_headroom = bool(has_headroom is True)
acceptance_mode = "absolute_non_regression" if meets and not has_headroom else "delta_uplift"
print(("1" if meets else "0") + "|" + ("1" if has_headroom else "0") + "|" + acceptance_mode)
PY
)"
BASELINE_MEETS_MINIMUM="${BASELINE_STATE%%|*}"
BASELINE_STATE_REST="${BASELINE_STATE#*|}"
BASELINE_HAS_HEADROOM="${BASELINE_STATE_REST%%|*}"
ACCEPTANCE_MODE="${BASELINE_STATE_REST#*|}"
DOWNSTREAM_STATE="$(python3 - "$CHALLENGE_SUMMARY" "$PACK_TRACK" "$ACCEPTANCE_SCOPE" "$CONTINUE_ON_WEAK_BASELINE" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
pack_track = str(sys.argv[2] or "").strip().lower()
acceptance_scope = str(sys.argv[3] or "").strip().lower()
continue_flag = str(sys.argv[4] or "").strip().lower() not in {"", "0", "false", "no", "off"}
reasons = {str(x) for x in (summary.get("reasons") if isinstance(summary.get("reasons"), list) else []) if str(x)}
meets = summary.get("baseline_meets_minimum")
if meets is None:
    meets = summary.get("baseline_in_target_range")
meets = meets is True
execution_valid = summary.get("baseline_execution_valid")
if execution_valid is None:
    execution_valid = "baseline_off_run_results_empty" not in reasons
execution_valid = execution_valid is True
realism_independent = pack_track == "realism" and acceptance_scope == "independent_validation"
continued = continue_flag and realism_independent and execution_valid and not meets
should_run = meets or continued
print(("1" if should_run else "0") + "|" + ("1" if continued else "0") + "|" + ("1" if execution_valid else "0"))
PY
)"
SHOULD_RUN_DOWNSTREAM="${DOWNSTREAM_STATE%%|*}"
DOWNSTREAM_STATE_REST="${DOWNSTREAM_STATE#*|}"
CONTINUED_AFTER_WEAK_BASELINE="${DOWNSTREAM_STATE_REST%%|*}"
BASELINE_EXECUTION_VALID="${DOWNSTREAM_STATE_REST#*|}"

MAIN_SWEEP_RC=0
NIGHT_SWEEP_RC=0
MAIN_L5_RC=0
NIGHT_L5_RC=0
MAIN_PROFILE="score_v1"

if [ "$SHOULD_RUN_DOWNSTREAM" = "1" ]; then
  set +e
  write_stage_status "main_sweep" "RUNNING" 0 "$MAIN_SWEEP_OUT/summary.json"
  run_sweep "$MAIN_PLANNER_BACKEND" "$MAIN_SWEEP_OUT" "$MAIN_SWEEP_EXECUTOR_CMD"
  MAIN_SWEEP_RC=$?
  set -e
  write_stage_status "main_sweep" "$(summary_status "$MAIN_SWEEP_OUT/summary.json" "$MAIN_SWEEP_RC")" "$MAIN_SWEEP_RC" "$MAIN_SWEEP_OUT/summary.json"

  if [ -f "$MAIN_SWEEP_OUT/summary.json" ]; then
    MAIN_PROFILE="$(python3 - "$MAIN_SWEEP_OUT/summary.json" <<'PY'
import json
import sys
from pathlib import Path
summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
profile = str(summary.get("recommended_profile") or "").strip()
print(profile if profile else "score_v1")
PY
)"
  fi

  if [ "$ENABLE_NIGHT" = "1" ]; then
    set +e
    write_stage_status "night_sweep" "RUNNING" 0 "$NIGHT_SWEEP_OUT/summary.json"
    run_sweep "$NIGHT_PLANNER_BACKEND" "$NIGHT_SWEEP_OUT" "$NIGHT_SWEEP_EXECUTOR_CMD"
    NIGHT_SWEEP_RC=$?
    set -e
    write_stage_status "night_sweep" "$(summary_status "$NIGHT_SWEEP_OUT/summary.json" "$NIGHT_SWEEP_RC")" "$NIGHT_SWEEP_RC" "$NIGHT_SWEEP_OUT/summary.json"
  else
    mkdir -p "$NIGHT_SWEEP_OUT"
    printf '{}\n' > "$NIGHT_SWEEP_OUT/summary.json"
    write_stage_status "night_sweep" "SKIPPED" 0 "$NIGHT_SWEEP_OUT/summary.json" "{\"reason\": \"lean_mode_night_disabled\"}"
  fi

  set +e
  write_stage_status "main_l5" "RUNNING" 0 "$MAIN_L5_OUT/l5_eval_summary.json"
  run_l5_eval "$MAIN_PLANNER_BACKEND" "$MAIN_GATE_MODE" "$MAIN_L5_OUT" "$MAIN_PROFILE" "$MAIN_L5_L3_EXECUTOR_CMD" "$MAIN_L5_L4_EXECUTOR_CMD"
  MAIN_L5_RC=$?
  set -e
  write_stage_status "main_l5" "$(summary_status "$MAIN_L5_OUT/l5_eval_summary.json" "$MAIN_L5_RC")" "$MAIN_L5_RC" "$MAIN_L5_OUT/l5_eval_summary.json"

  if [ "$ENABLE_NIGHT" = "1" ]; then
    set +e
    write_stage_status "night_l5" "RUNNING" 0 "$NIGHT_L5_OUT/l5_eval_summary.json"
    run_l5_eval "$NIGHT_PLANNER_BACKEND" "$NIGHT_GATE_MODE" "$NIGHT_L5_OUT" "$MAIN_PROFILE" "$NIGHT_L5_L3_EXECUTOR_CMD" "$NIGHT_L5_L4_EXECUTOR_CMD"
    NIGHT_L5_RC=$?
    set -e
    write_stage_status "night_l5" "$(summary_status "$NIGHT_L5_OUT/l5_eval_summary.json" "$NIGHT_L5_RC")" "$NIGHT_L5_RC" "$NIGHT_L5_OUT/l5_eval_summary.json"
  else
    mkdir -p "$NIGHT_L5_OUT"
    printf '{}\n' > "$NIGHT_L5_OUT/l5_eval_summary.json"
    printf '{}\n' > "$NIGHT_L5_OUT/l5_weekly_metrics.json"
    write_stage_status "night_l5" "SKIPPED" 0 "$NIGHT_L5_OUT/l5_eval_summary.json" "{\"reason\": \"lean_mode_night_disabled\"}"
  fi
else
  mkdir -p "$MAIN_SWEEP_OUT" "$NIGHT_SWEEP_OUT" "$MAIN_L5_OUT" "$NIGHT_L5_OUT"
  printf '{}\n' > "$MAIN_SWEEP_OUT/summary.json"
  printf '{}\n' > "$NIGHT_SWEEP_OUT/summary.json"
  printf '{}\n' > "$MAIN_L5_OUT/l5_eval_summary.json"
  printf '{}\n' > "$MAIN_L5_OUT/l5_weekly_metrics.json"
  printf '{}\n' > "$NIGHT_L5_OUT/l5_eval_summary.json"
  printf '{}\n' > "$NIGHT_L5_OUT/l5_weekly_metrics.json"
  write_stage_status "main_sweep" "SKIPPED" 0 "$MAIN_SWEEP_OUT/summary.json"
  write_stage_status "night_sweep" "SKIPPED" 0 "$NIGHT_SWEEP_OUT/summary.json"
  write_stage_status "main_l5" "SKIPPED" 0 "$MAIN_L5_OUT/l5_eval_summary.json"
  write_stage_status "night_l5" "SKIPPED" 0 "$NIGHT_L5_OUT/l5_eval_summary.json"
fi

DECISION_JSON="$OUT_DIR/decision_summary.json"
DECISION_MD="$OUT_DIR/decision_summary.md"
python3 -m gateforge.agent_modelica_l4_uplift_decision_v0 \
  --challenge-summary "$CHALLENGE_SUMMARY" \
  --main-sweep-summary "$MAIN_SWEEP_OUT/summary.json" \
  --main-l5-summary "$MAIN_L5_OUT/l5_eval_summary.json" \
  --main-weekly-summary "$MAIN_L5_OUT/l5_weekly_metrics.json" \
  --night-sweep-summary "$NIGHT_SWEEP_OUT/summary.json" \
  --night-l5-summary "$NIGHT_L5_OUT/l5_eval_summary.json" \
  --night-weekly-summary "$NIGHT_L5_OUT/l5_weekly_metrics.json" \
  --min-delta-success-pp "$MIN_DELTA_SUCCESS_PP" \
  --absolute-success-target-pct "$ABSOLUTE_SUCCESS_TARGET_PCT" \
  --non-regression-tolerance-pp "$NON_REGRESSION_TOLERANCE_PP" \
  --max-regression-worsen-pp "$MAX_REGRESSION_WORSEN_PP" \
  --max-physics-worsen-pp "$MAX_PHYSICS_WORSEN_PP" \
  --night-enabled "$ENABLE_NIGHT" \
  --out "$DECISION_JSON" \
  --report-out "$DECISION_MD"

python3 - "$OUT_DIR" "$CHALLENGE_SUMMARY" "$DECISION_JSON" "$MAIN_SWEEP_OUT/summary.json" "$NIGHT_SWEEP_OUT/summary.json" "$MAIN_L5_OUT/l5_eval_summary.json" "$MAIN_L5_OUT/l5_weekly_metrics.json" "$NIGHT_L5_OUT/l5_eval_summary.json" "$NIGHT_L5_OUT/l5_weekly_metrics.json" "$CHALLENGE_RC" "$MAIN_SWEEP_RC" "$NIGHT_SWEEP_RC" "$MAIN_L5_RC" "$NIGHT_L5_RC" "$MAIN_PROFILE" "$CONTINUED_AFTER_WEAK_BASELINE" "$BASELINE_EXECUTION_VALID" "$REALISM_MODE" "$ENABLE_NIGHT" "$LIVE_LEDGER_PATH" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out_dir = Path(sys.argv[1])
challenge_summary_path = Path(sys.argv[2])
decision_path = Path(sys.argv[3])
main_sweep_path = Path(sys.argv[4])
night_sweep_path = Path(sys.argv[5])
main_l5_path = Path(sys.argv[6])
main_weekly_path = Path(sys.argv[7])
night_l5_path = Path(sys.argv[8])
night_weekly_path = Path(sys.argv[9])
challenge_rc = int(sys.argv[10])
main_sweep_rc = int(sys.argv[11])
night_sweep_rc = int(sys.argv[12])
main_l5_rc = int(sys.argv[13])
night_l5_rc = int(sys.argv[14])
main_profile = str(sys.argv[15] or "").strip()
continued_after_weak_baseline = str(sys.argv[16] or "") == "1"
baseline_execution_valid = str(sys.argv[17] or "") == "1"
realism_mode = str(sys.argv[18] or "").strip()
night_enabled = str(sys.argv[19] or "") == "1"
live_ledger_path = Path(sys.argv[20])

def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}

challenge = _load(challenge_summary_path)
decision = _load(decision_path)
main_sweep = _load(main_sweep_path)
night_sweep = _load(night_sweep_path)
main_l5 = _load(main_l5_path)
main_weekly = _load(main_weekly_path)
night_l5 = _load(night_l5_path)
night_weekly = _load(night_weekly_path)
live_ledger = _load(live_ledger_path)

missing = []
for label, payload in (
    ("challenge_summary", challenge),
    ("decision_summary", decision),
):
    if not payload:
        missing.append(label)

baseline_meets_minimum = challenge.get("baseline_meets_minimum") is True
baseline_has_headroom = challenge.get("baseline_has_headroom") is True
baseline_eligible_for_uplift = challenge.get("baseline_eligible_for_uplift")
if baseline_eligible_for_uplift is None:
    baseline_eligible_for_uplift = baseline_meets_minimum and baseline_has_headroom
acceptance_mode = str(decision.get("acceptance_mode") or ("absolute_non_regression" if baseline_meets_minimum and not baseline_has_headroom else "delta_uplift"))
if baseline_meets_minimum or continued_after_weak_baseline:
    required_payloads = [
        ("main_sweep_summary", main_sweep),
        ("main_l5_eval_summary", main_l5),
        ("main_weekly_summary", main_weekly),
    ]
    if night_enabled:
        required_payloads.extend(
            [
                ("night_sweep_summary", night_sweep),
                ("night_l5_eval_summary", night_l5),
                ("night_weekly_summary", night_weekly),
            ]
        )
    for label, payload in required_payloads:
        if not payload:
            missing.append(label)

status = "PASS" if not missing else "FAIL"
reasons = []
if challenge_rc != 0 and not challenge:
    reasons.append("challenge_script_nonzero_exit")
if main_sweep_rc != 0 and not main_sweep:
    reasons.append("main_sweep_script_nonzero_exit")
if night_enabled and night_sweep_rc != 0 and not night_sweep:
    reasons.append("night_sweep_script_nonzero_exit")
if main_l5_rc != 0 and not main_l5:
    reasons.append("main_l5_script_nonzero_exit")
if night_enabled and night_l5_rc != 0 and not night_l5:
    reasons.append("night_l5_script_nonzero_exit")
if missing:
    reasons.extend([f"missing_{x}" for x in sorted(set(missing))])

if not night_enabled:
    reasons = [
        x
        for x in reasons
        if x
        not in {
            "missing_night_sweep_summary",
            "missing_night_l5_eval_summary",
            "missing_night_weekly_summary",
            "night_sweep_script_nonzero_exit",
            "night_l5_script_nonzero_exit",
        }
    ]
    missing = [
        x
        for x in missing
        if x
        not in {
            "night_sweep_summary",
            "night_l5_eval_summary",
            "night_weekly_summary",
        }
    ]
    status = "PASS" if not missing else "FAIL"

bundle = {
    "schema_version": "agent_modelica_l4_uplift_evidence_bundle_v0",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "pack_id": str(challenge.get("pack_id") or ""),
    "pack_version": str(challenge.get("pack_version") or ""),
    "pack_track": str(challenge.get("pack_track") or ""),
    "acceptance_scope": str(challenge.get("acceptance_scope") or ""),
    "decision": str(decision.get("decision") or ""),
    "primary_reason": str(decision.get("primary_reason") or "none"),
    "acceptance_mode": acceptance_mode,
    "baseline_meets_minimum": baseline_meets_minimum,
    "baseline_has_headroom": baseline_has_headroom,
    "baseline_execution_valid": baseline_execution_valid,
    "continued_after_weak_baseline": continued_after_weak_baseline,
    "realism_mode": realism_mode or "full",
    "night_enabled": night_enabled,
    "live_budget": {
        "max_requests_per_run": int((live_ledger.get("live_budget") or {}).get("max_requests_per_run") or 0) if isinstance(live_ledger.get("live_budget"), dict) else None,
        "max_consecutive_429": int((live_ledger.get("live_budget") or {}).get("max_consecutive_429") or 0) if isinstance(live_ledger.get("live_budget"), dict) else None,
        "base_backoff_sec": (live_ledger.get("live_budget") or {}).get("base_backoff_sec") if isinstance(live_ledger.get("live_budget"), dict) else None,
        "max_backoff_sec": (live_ledger.get("live_budget") or {}).get("max_backoff_sec") if isinstance(live_ledger.get("live_budget"), dict) else None,
    },
    "live_request_count": int(live_ledger.get("request_count") or 0),
    "rate_limit_429_count": int(live_ledger.get("rate_limit_429_count") or 0),
    "budget_stop_triggered": bool(live_ledger.get("budget_stop_triggered")),
    "live_budget_stop_reason": str(live_ledger.get("last_stop_reason") or ""),
    "baseline_headroom_max_pct": challenge.get("baseline_target_range_pct", {}).get("max") if isinstance(challenge.get("baseline_target_range_pct"), dict) else None,
    "baseline_eligible_for_uplift": baseline_eligible_for_uplift,
    "baseline_in_target_range": challenge.get("baseline_in_target_range"),
    "main_recommended_profile": main_profile or str(main_sweep.get("recommended_profile") or ""),
    "main_success_at_k_pct": decision.get("main_success_at_k_pct"),
    "absolute_success_target_pct": decision.get("absolute_success_target_pct"),
    "main_delta_success_at_k_pp": decision.get("main_delta_success_at_k_pp"),
    "non_regression_ok": decision.get("non_regression_ok"),
    "main_delta_regression_fail_rate_pp": decision.get("main_delta_regression_fail_rate_pp"),
    "main_delta_physics_fail_rate_pp": decision.get("main_delta_physics_fail_rate_pp"),
    "infra_failure_count_total": decision.get("infra_failure_count_total"),
    "counts_by_failure_type": challenge.get("counts_by_failure_type") if isinstance(challenge.get("counts_by_failure_type"), dict) else {},
    "counts_by_category": challenge.get("counts_by_category") if isinstance(challenge.get("counts_by_category"), dict) else {},
    "main_gate_result": decision.get("main_gate_result"),
    "main_weekly_recommendation": decision.get("main_weekly_recommendation"),
    "main_weekly_recommendation_reason": decision.get("main_weekly_recommendation_reason"),
    "consistency_ok": decision.get("consistency_ok"),
    "script_exit_codes": {
        "challenge": challenge_rc,
        "main_sweep": main_sweep_rc,
        "night_sweep": night_sweep_rc,
        "main_l5_eval": main_l5_rc,
        "night_l5_eval": night_l5_rc,
    },
    "reasons": sorted(
        set(
            [str(x) for x in reasons if str(x)]
            + [str(x) for x in (decision.get("reasons") or []) if str(x)]
        )
    ),
    "paths": {
        "challenge_summary": str(challenge_summary_path),
        "main_sweep_summary": str(main_sweep_path),
        "night_sweep_summary": str(night_sweep_path),
        "main_l5_eval_summary": str(main_l5_path),
        "main_weekly_summary": str(main_weekly_path),
        "night_l5_eval_summary": str(night_l5_path),
        "night_weekly_summary": str(night_weekly_path),
        "decision_summary": str(decision_path),
    },
}

if bundle.get("live_budget_stop_reason") in {"live_request_budget_exceeded", "rate_limited"}:
    bundle["primary_reason"] = str(bundle.get("live_budget_stop_reason"))

summary_json = out_dir / "summary.json"
summary_md = out_dir / "summary.md"
summary_json.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
summary_md.write_text(
    "\n".join(
        [
            "# Agent Modelica L4 Uplift Evidence v0",
            "",
            f"- status: `{bundle.get('status')}`",
            f"- decision: `{bundle.get('decision')}`",
            f"- primary_reason: `{bundle.get('primary_reason')}`",
            f"- acceptance_mode: `{bundle.get('acceptance_mode')}`",
            f"- realism_mode: `{bundle.get('realism_mode')}`",
            f"- night_enabled: `{bundle.get('night_enabled')}`",
            f"- baseline_meets_minimum: `{bundle.get('baseline_meets_minimum')}`",
            f"- baseline_has_headroom: `{bundle.get('baseline_has_headroom')}`",
            f"- baseline_eligible_for_uplift: `{bundle.get('baseline_eligible_for_uplift')}`",
            f"- baseline_in_target_range: `{bundle.get('baseline_in_target_range')}`",
            f"- main_recommended_profile: `{bundle.get('main_recommended_profile')}`",
            f"- main_success_at_k_pct: `{bundle.get('main_success_at_k_pct')}`",
            f"- absolute_success_target_pct: `{bundle.get('absolute_success_target_pct')}`",
            f"- main_delta_success_at_k_pp: `{bundle.get('main_delta_success_at_k_pp')}`",
            f"- non_regression_ok: `{bundle.get('non_regression_ok')}`",
            f"- infra_failure_count_total: `{bundle.get('infra_failure_count_total')}`",
            f"- live_request_count: `{bundle.get('live_request_count')}`",
            f"- rate_limit_429_count: `{bundle.get('rate_limit_429_count')}`",
            f"- budget_stop_triggered: `{bundle.get('budget_stop_triggered')}`",
            f"- reasons: `{bundle.get('reasons')}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps(bundle))
if bundle.get("status") != "PASS":
    raise SystemExit(1)
PY

if [ "$ENFORCE_PROMOTE" = "1" ]; then
  DECISION_VALUE="$(python3 - "$DECISION_JSON" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(str(payload.get("decision") or ""))
PY
)"
  if [ "$DECISION_VALUE" != "promote" ]; then
    echo "L4 uplift decision is not promote: $DECISION_VALUE" >&2
    exit 1
  fi
fi

cat "$OUT_DIR/summary.json"
