#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_OUT_DIR:-artifacts/agent_modelica_l4_canonical_baseline_v0}"
BASE_TASKSET="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_BASE_TASKSET:-assets_private/agent_modelica_l4_challenge_pack_v0/taskset_frozen.json}"
BUDGETS="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_BUDGETS:-1x120,1x180,2x90,2x120,2x150,2x165}"
REPEAT_COUNT="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_REPEAT_COUNT:-2}"
REUSE_EXISTING="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_REUSE_EXISTING:-1}"
TARGET_MIN_OFF_SUCCESS_PCT="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_TARGET_MIN_OFF_SUCCESS_PCT:-60}"
MIN_UPLIFT_DELTA_PP="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_MIN_UPLIFT_DELTA_PP:-5}"
REQUIRED_TOTAL_RUNS="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_REQUIRED_TOTAL_RUNS:-3}"
MIN_IN_RANGE_RUNS="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_MIN_IN_RANGE_RUNS:-2}"
MAX_REPEAT_SPREAD_PP="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_MAX_REPEAT_SPREAD_PP:-20}"
ENFORCE_READY="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_ENFORCE_READY:-0}"

SCALES="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_SCALES:-small,medium}"
FAILURE_TYPES="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_FAILURE_TYPES:-model_check_error,simulate_error,semantic_regression}"
PER_FAILURE_TYPE_CAP="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_PER_FAILURE_TYPE_CAP:-6}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_SPLIT_SEED:-agent_modelica_l4_challenge_v0}"

BASELINE_PLANNER_BACKEND="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_PLANNER_BACKEND:-gemini}"
BASELINE_LLM_MODEL="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_LLM_MODEL:-${LLM_MODEL:-${GATEFORGE_GEMINI_MODEL:-}}}"
BACKEND="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_BACKEND:-openmodelica_docker}"
OM_DOCKER_IMAGE="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_LIVE_TIMEOUT_SEC:-90}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_LIVE_MAX_OUTPUT_CHARS:-2400}"
LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_CANONICAL_BASELINE_LIVE_EXECUTOR_CMD:-}"

RUNS_DIR="$OUT_DIR/candidates"
SUMMARY_PATH="$OUT_DIR/summary.json"
REPORT_PATH="$OUT_DIR/summary.md"
RUN_MANIFEST_PATH="$OUT_DIR/run_manifest.json"
TARGET_MAX_OFF_SUCCESS_PCT="$(python3 - "$MIN_UPLIFT_DELTA_PP" <<'PY'
import sys
delta = float(sys.argv[1] or 5.0)
print(max(0.0, 100.0 - delta))
PY
)"
PROVISIONAL_SUMMARY_PATH="$OUT_DIR/.provisional_summary.json"

if [ ! -f "$BASE_TASKSET" ]; then
  echo "Missing base taskset: $BASE_TASKSET" >&2
  exit 1
fi

mkdir -p "$RUNS_DIR"

has_complete_run() {
  local dir="$1"
  [ -f "$dir/frozen_summary.json" ] && \
  [ -f "$dir/manifest.json" ] && \
  [ -f "$dir/baseline_off_run_summary.json" ] && \
  [ -f "$dir/baseline_off_run_results.json" ]
}

run_budget_dir() {
  local budget_token="$1"
  local out_dir="$2"
  local max_rounds="$3"
  local max_time_sec="$4"
  if [ "$REUSE_EXISTING" = "1" ] && has_complete_run "$out_dir"; then
    return 0
  fi
  rm -rf "$out_dir"
  if [ -n "$LIVE_EXECUTOR_CMD" ]; then
    GATEFORGE_AGENT_L4_CHALLENGE_OUT_DIR="$out_dir" \
    GATEFORGE_AGENT_L4_CHALLENGE_BASE_TASKSET="$BASE_TASKSET" \
    GATEFORGE_AGENT_L4_CHALLENGE_SCALES="$SCALES" \
    GATEFORGE_AGENT_L4_CHALLENGE_FAILURE_TYPES="$FAILURE_TYPES" \
    GATEFORGE_AGENT_L4_CHALLENGE_PER_FAILURE_TYPE_CAP="$PER_FAILURE_TYPE_CAP" \
    GATEFORGE_AGENT_L4_CHALLENGE_HOLDOUT_RATIO="$HOLDOUT_RATIO" \
    GATEFORGE_AGENT_L4_CHALLENGE_SPLIT_SEED="$SPLIT_SEED" \
    GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MIN_OFF_SUCCESS_PCT="$TARGET_MIN_OFF_SUCCESS_PCT" \
    GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MAX_OFF_SUCCESS_PCT="$TARGET_MAX_OFF_SUCCESS_PCT" \
    GATEFORGE_AGENT_L4_CHALLENGE_ENFORCE_BASELINE_RANGE="0" \
    GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_PLANNER_BACKEND="$BASELINE_PLANNER_BACKEND" \
    GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_LLM_MODEL="$BASELINE_LLM_MODEL" \
    GATEFORGE_AGENT_L4_CHALLENGE_BACKEND="$BACKEND" \
    GATEFORGE_AGENT_L4_CHALLENGE_OM_DOCKER_IMAGE="$OM_DOCKER_IMAGE" \
    GATEFORGE_AGENT_L4_CHALLENGE_MAX_ROUNDS="$max_rounds" \
    GATEFORGE_AGENT_L4_CHALLENGE_MAX_TIME_SEC="$max_time_sec" \
    GATEFORGE_AGENT_L4_CHALLENGE_RUNTIME_THRESHOLD="$RUNTIME_THRESHOLD" \
    GATEFORGE_AGENT_L4_CHALLENGE_LIVE_TIMEOUT_SEC="$LIVE_TIMEOUT_SEC" \
    GATEFORGE_AGENT_L4_CHALLENGE_LIVE_MAX_OUTPUT_CHARS="$LIVE_MAX_OUTPUT_CHARS" \
    GATEFORGE_AGENT_L4_CHALLENGE_LIVE_EXECUTOR_CMD="$LIVE_EXECUTOR_CMD" \
    bash scripts/run_agent_modelica_l4_challenge_pack_v0.sh
  else
    GATEFORGE_AGENT_L4_CHALLENGE_OUT_DIR="$out_dir" \
    GATEFORGE_AGENT_L4_CHALLENGE_BASE_TASKSET="$BASE_TASKSET" \
    GATEFORGE_AGENT_L4_CHALLENGE_SCALES="$SCALES" \
    GATEFORGE_AGENT_L4_CHALLENGE_FAILURE_TYPES="$FAILURE_TYPES" \
    GATEFORGE_AGENT_L4_CHALLENGE_PER_FAILURE_TYPE_CAP="$PER_FAILURE_TYPE_CAP" \
    GATEFORGE_AGENT_L4_CHALLENGE_HOLDOUT_RATIO="$HOLDOUT_RATIO" \
    GATEFORGE_AGENT_L4_CHALLENGE_SPLIT_SEED="$SPLIT_SEED" \
    GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MIN_OFF_SUCCESS_PCT="$TARGET_MIN_OFF_SUCCESS_PCT" \
    GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MAX_OFF_SUCCESS_PCT="$TARGET_MAX_OFF_SUCCESS_PCT" \
    GATEFORGE_AGENT_L4_CHALLENGE_ENFORCE_BASELINE_RANGE="0" \
    GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_PLANNER_BACKEND="$BASELINE_PLANNER_BACKEND" \
    GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_LLM_MODEL="$BASELINE_LLM_MODEL" \
    GATEFORGE_AGENT_L4_CHALLENGE_BACKEND="$BACKEND" \
    GATEFORGE_AGENT_L4_CHALLENGE_OM_DOCKER_IMAGE="$OM_DOCKER_IMAGE" \
    GATEFORGE_AGENT_L4_CHALLENGE_MAX_ROUNDS="$max_rounds" \
    GATEFORGE_AGENT_L4_CHALLENGE_MAX_TIME_SEC="$max_time_sec" \
    GATEFORGE_AGENT_L4_CHALLENGE_RUNTIME_THRESHOLD="$RUNTIME_THRESHOLD" \
    GATEFORGE_AGENT_L4_CHALLENGE_LIVE_TIMEOUT_SEC="$LIVE_TIMEOUT_SEC" \
    GATEFORGE_AGENT_L4_CHALLENGE_LIVE_MAX_OUTPUT_CHARS="$LIVE_MAX_OUTPUT_CHARS" \
    bash scripts/run_agent_modelica_l4_challenge_pack_v0.sh
  fi
}

summary_meets_minimum() {
  local path="$1"
  python3 - "$path" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
meets = payload.get("baseline_meets_minimum")
if meets is None:
    meets = payload.get("baseline_in_target_range")
print("1" if meets is True else "0")
PY
}

RUN_DIRS=()
SELECTED_BUDGET=""
SELECTED_ROUNDS=""
SELECTED_TIME=""

IFS=',' read -r -a BUDGET_TOKENS <<< "$BUDGETS"
for raw_budget in "${BUDGET_TOKENS[@]}"; do
  budget="$(echo "$raw_budget" | tr -d '[:space:]')"
  if [[ ! "$budget" =~ ^([0-9]+)x([0-9]+)$ ]]; then
    echo "Invalid budget token: $budget" >&2
    exit 1
  fi
  max_rounds="${BASH_REMATCH[1]}"
  max_time_sec="${BASH_REMATCH[2]}"
  out_dir="$RUNS_DIR/mr${max_rounds}_mt${max_time_sec}"
  run_budget_dir "$budget" "$out_dir" "$max_rounds" "$max_time_sec"
  RUN_DIRS+=("$out_dir")
  if [ -z "$SELECTED_BUDGET" ]; then
    meets_minimum="$(summary_meets_minimum "$out_dir/frozen_summary.json")"
    if [ "$meets_minimum" = "1" ]; then
      SELECTED_BUDGET="$budget"
      SELECTED_ROUNDS="$max_rounds"
      SELECTED_TIME="$max_time_sec"
      repeat_idx=1
      while [ "$repeat_idx" -le "$REPEAT_COUNT" ]; do
        repeat_dir="$RUNS_DIR/mr${SELECTED_ROUNDS}_mt${SELECTED_TIME}_r${repeat_idx}"
        run_budget_dir "$SELECTED_BUDGET" "$repeat_dir" "$SELECTED_ROUNDS" "$SELECTED_TIME"
        RUN_DIRS+=("$repeat_dir")
        repeat_idx=$((repeat_idx + 1))
      done

      DECISION_ARGS=()
      for dir in "${RUN_DIRS[@]}"; do
        DECISION_ARGS+=(--candidate-dir "$dir")
      done
      python3 -m gateforge.agent_modelica_l4_canonical_baseline_v0 \
        "${DECISION_ARGS[@]}" \
        --target-min-off-success-pct "$TARGET_MIN_OFF_SUCCESS_PCT" \
        --min-uplift-delta-pp "$MIN_UPLIFT_DELTA_PP" \
        --required-total-runs "$REQUIRED_TOTAL_RUNS" \
        --min-in-range-runs "$MIN_IN_RANGE_RUNS" \
        --max-repeat-spread-pp "$MAX_REPEAT_SPREAD_PP" \
        --out "$PROVISIONAL_SUMMARY_PATH" >/dev/null
      provisional_status="$(python3 - "$PROVISIONAL_SUMMARY_PATH" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(f"{payload.get('decision') or ''}|{payload.get('primary_reason') or ''}")
PY
)"
      provisional_decision="${provisional_status%%|*}"
      provisional_reason="${provisional_status#*|}"
      if [ "$provisional_decision" = "ready" ] || [ "$provisional_reason" = "baseline_saturated_no_headroom" ]; then
        break
      fi
      SELECTED_BUDGET=""
      SELECTED_ROUNDS=""
      SELECTED_TIME=""
    fi
  fi
done

DECISION_ARGS=()
for dir in "${RUN_DIRS[@]}"; do
  DECISION_ARGS+=(--candidate-dir "$dir")
done

python3 -m gateforge.agent_modelica_l4_canonical_baseline_v0 \
  "${DECISION_ARGS[@]}" \
  --target-min-off-success-pct "$TARGET_MIN_OFF_SUCCESS_PCT" \
  --min-uplift-delta-pp "$MIN_UPLIFT_DELTA_PP" \
  --required-total-runs "$REQUIRED_TOTAL_RUNS" \
  --min-in-range-runs "$MIN_IN_RANGE_RUNS" \
  --max-repeat-spread-pp "$MAX_REPEAT_SPREAD_PP" \
  --out "$SUMMARY_PATH" \
  --report-out "$REPORT_PATH"

python3 - "$RUN_MANIFEST_PATH" "$BASE_TASKSET" "$BUDGETS" "$SELECTED_BUDGET" "$SUMMARY_PATH" "${RUN_DIRS[@]}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out_path = Path(sys.argv[1])
base_taskset = str(sys.argv[2] or "")
budgets = [x.strip() for x in str(sys.argv[3] or "").split(",") if x.strip()]
selected_budget = str(sys.argv[4] or "")
summary_path = str(sys.argv[5] or "")
run_dirs = [str(x) for x in sys.argv[6:]]
payload = {
    "schema_version": "agent_modelica_l4_canonical_baseline_run_manifest_v0",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "base_taskset": base_taskset,
    "budgets": budgets,
    "selected_budget": selected_budget or None,
    "summary_path": summary_path,
    "candidate_dirs": run_dirs,
}
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

rm -f "$PROVISIONAL_SUMMARY_PATH"

if [ "$ENFORCE_READY" = "1" ]; then
  python3 - "$SUMMARY_PATH" <<'PY'
import json
import sys
from pathlib import Path
summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if str(summary.get("decision") or "") != "ready":
    raise SystemExit(1)
PY
fi

cat "$SUMMARY_PATH"
