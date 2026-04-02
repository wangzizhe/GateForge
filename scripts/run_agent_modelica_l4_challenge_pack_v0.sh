#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L4_CHALLENGE_OUT_DIR:-assets_private/agent_modelica_l4_challenge_pack_v0}"
BASE_TASKSET="${GATEFORGE_AGENT_L4_CHALLENGE_BASE_TASKSET:-assets_private/agent_modelica_l2_freeze_pack_v0/taskset_frozen.json}"
SCALES="${GATEFORGE_AGENT_L4_CHALLENGE_SCALES:-small,medium}"
FAILURE_TYPES="${GATEFORGE_AGENT_L4_CHALLENGE_FAILURE_TYPES:-model_check_error,simulate_error,semantic_regression}"
REQUIRED_CATEGORIES="${GATEFORGE_AGENT_L4_CHALLENGE_REQUIRED_CATEGORIES:-}"
PER_FAILURE_TYPE_CAP="${GATEFORGE_AGENT_L4_CHALLENGE_PER_FAILURE_TYPE_CAP:-6}"
SPLIT_SEED="${GATEFORGE_AGENT_L4_CHALLENGE_SPLIT_SEED:-agent_modelica_l4_challenge_v0}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_L4_CHALLENGE_HOLDOUT_RATIO:-0.15}"
TARGET_MIN_OFF_SUCCESS_PCT="${GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MIN_OFF_SUCCESS_PCT:-60}"
TARGET_MAX_OFF_SUCCESS_PCT="${GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MAX_OFF_SUCCESS_PCT:-95}"
ENFORCE_BASELINE_RANGE="${GATEFORGE_AGENT_L4_CHALLENGE_ENFORCE_BASELINE_RANGE:-1}"
PACK_ID="${GATEFORGE_AGENT_L4_CHALLENGE_PACK_ID:-}"
PACK_VERSION="${GATEFORGE_AGENT_L4_CHALLENGE_PACK_VERSION:-}"
PACK_TRACK="${GATEFORGE_AGENT_L4_CHALLENGE_PACK_TRACK:-}"
ACCEPTANCE_SCOPE="${GATEFORGE_AGENT_L4_CHALLENGE_ACCEPTANCE_SCOPE:-}"

PLANNER_BACKEND="${GATEFORGE_AGENT_L4_CHALLENGE_PLANNER_BACKEND:-rule}"
BACKEND="${GATEFORGE_AGENT_L4_CHALLENGE_BACKEND:-openmodelica_docker}"
OM_DOCKER_IMAGE="${GATEFORGE_AGENT_L4_CHALLENGE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"
MAX_ROUNDS="${GATEFORGE_AGENT_L4_CHALLENGE_MAX_ROUNDS:-1}"
MAX_TIME_SEC="${GATEFORGE_AGENT_L4_CHALLENGE_MAX_TIME_SEC:-120}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_L4_CHALLENGE_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_L4_CHALLENGE_LIVE_TIMEOUT_SEC:-90}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_L4_CHALLENGE_LIVE_MAX_OUTPUT_CHARS:-1600}"
BASELINE_PLANNER_BACKEND="${GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_PLANNER_BACKEND:-auto}"
BASELINE_LLM_MODEL="${GATEFORGE_AGENT_L4_CHALLENGE_BASELINE_LLM_MODEL:-${LLM_MODEL:-}}"
LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_CHALLENGE_LIVE_EXECUTOR_CMD:-python3 -m gateforge.agent_modelica_live_executor_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${BASELINE_PLANNER_BACKEND}\" --backend \"${BACKEND}\" --docker-image \"${OM_DOCKER_IMAGE}\"}"
BASELINE_RUN_SUMMARY="$OUT_DIR/baseline_off_run_summary.json"
BASELINE_RUN_RESULTS="$OUT_DIR/baseline_off_run_results.json"
BASELINE_CMD_SHA256="$(python3 - "$LIVE_EXECUTOR_CMD" <<'PY'
import hashlib
import sys
print(hashlib.sha256(sys.argv[1].encode("utf-8")).hexdigest())
PY
)"
GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || true)"

if [ ! -f "$BASE_TASKSET" ]; then
  echo "Missing base taskset: $BASE_TASKSET" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_l4_challenge_pack_v0 \
  --taskset-in "$BASE_TASKSET" \
  --out-dir "$OUT_DIR" \
  --scales "$SCALES" \
  --failure-types "$FAILURE_TYPES" \
  --required-categories "$REQUIRED_CATEGORIES" \
  --pack-id "$PACK_ID" \
  --pack-version "$PACK_VERSION" \
  --pack-track "$PACK_TRACK" \
  --acceptance-scope "$ACCEPTANCE_SCOPE" \
  --per-failure-type-cap "$PER_FAILURE_TYPE_CAP" \
  --holdout-ratio "$HOLDOUT_RATIO" \
  --split-seed "$SPLIT_SEED" \
  --target-min-off-success-pct "$TARGET_MIN_OFF_SUCCESS_PCT" \
  --target-max-off-success-pct "$TARGET_MAX_OFF_SUCCESS_PCT" \
  --out "$OUT_DIR/frozen_summary.json" \
  --report-out "$OUT_DIR/frozen_summary.md"

set +e
if [ -n "$BASELINE_LLM_MODEL" ]; then
  env LLM_MODEL="$BASELINE_LLM_MODEL" python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset "$OUT_DIR/taskset_frozen.json" \
  --mode live \
  --max-rounds "$MAX_ROUNDS" \
  --max-time-sec "$MAX_TIME_SEC" \
  --runtime-threshold "$RUNTIME_THRESHOLD" \
  --live-executor-cmd "$LIVE_EXECUTOR_CMD" \
  --live-timeout-sec "$LIVE_TIMEOUT_SEC" \
  --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS" \
  --l4-enabled off \
  --results-out "$BASELINE_RUN_RESULTS" \
  --out "$BASELINE_RUN_SUMMARY"
else
  python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset "$OUT_DIR/taskset_frozen.json" \
  --mode live \
  --max-rounds "$MAX_ROUNDS" \
  --max-time-sec "$MAX_TIME_SEC" \
  --runtime-threshold "$RUNTIME_THRESHOLD" \
  --live-executor-cmd "$LIVE_EXECUTOR_CMD" \
  --live-timeout-sec "$LIVE_TIMEOUT_SEC" \
  --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS" \
  --l4-enabled off \
  --results-out "$BASELINE_RUN_RESULTS" \
  --out "$BASELINE_RUN_SUMMARY"
fi
BASELINE_RC=$?
set -e

BASELINE_RECORD_COUNT="$(python3 - "$BASELINE_RUN_RESULTS" <<'PY'
import json
import sys
from pathlib import Path

p = Path(sys.argv[1])
count = 0
if p.exists():
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        payload = None
    rows = []
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        maybe_rows = payload.get("records")
        if isinstance(maybe_rows, list):
            rows = maybe_rows
        else:
            maybe_rows = payload.get("rows")
            if isinstance(maybe_rows, list):
                rows = maybe_rows
    count = len([row for row in rows if isinstance(row, dict)])
print(count)
PY
)"

BASELINE_OFF_SUCCESS=""
if [ "$BASELINE_RECORD_COUNT" != "0" ] && [ -f "$BASELINE_RUN_SUMMARY" ]; then
  BASELINE_OFF_SUCCESS="$(python3 - "$BASELINE_RUN_SUMMARY" <<'PY'
import json
import sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.exists():
    print("")
else:
    d = json.loads(p.read_text(encoding="utf-8"))
    v = d.get("success_at_k_pct")
    print("" if v is None else str(v))
PY
)"
fi

SUMMARY_REFRESH_RC=0
if [ "$BASELINE_RECORD_COUNT" = "0" ]; then
  python3 - "$OUT_DIR/frozen_summary.json" "$BASELINE_RECORD_COUNT" <<'PY'
import json
import sys
from pathlib import Path

summary_path = Path(sys.argv[1])
record_count = int(sys.argv[2])
summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
reasons = summary.get("reasons") if isinstance(summary.get("reasons"), list) else []
for reason in ("baseline_off_run_results_empty", "baseline_execution_failed"):
    if reason not in reasons:
        reasons.append(reason)
summary["reasons"] = sorted(set([str(x) for x in reasons if str(x)]))
summary["status"] = "FAIL"
summary["baseline_off_success_at_k_pct"] = None
summary["baseline_off_record_count"] = record_count
summary["baseline_execution_valid"] = False
summary["baseline_meets_minimum"] = None
summary["baseline_has_headroom"] = None
summary["baseline_eligible_for_uplift"] = None
summary["baseline_in_target_range"] = None
summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"status": summary.get("status"), "baseline_off_record_count": record_count}))
PY
  SUMMARY_REFRESH_RC=2
elif [ -n "$BASELINE_OFF_SUCCESS" ]; then
  set +e
  python3 -m gateforge.agent_modelica_l4_challenge_pack_v0 \
    --taskset-in "$BASE_TASKSET" \
    --out-dir "$OUT_DIR" \
    --scales "$SCALES" \
    --failure-types "$FAILURE_TYPES" \
    --required-categories "$REQUIRED_CATEGORIES" \
    --pack-id "$PACK_ID" \
    --pack-version "$PACK_VERSION" \
    --pack-track "$PACK_TRACK" \
    --acceptance-scope "$ACCEPTANCE_SCOPE" \
    --per-failure-type-cap "$PER_FAILURE_TYPE_CAP" \
    --holdout-ratio "$HOLDOUT_RATIO" \
    --split-seed "$SPLIT_SEED" \
    --baseline-off-success-at-k-pct "$BASELINE_OFF_SUCCESS" \
    --baseline-off-record-count "$BASELINE_RECORD_COUNT" \
    --target-min-off-success-pct "$TARGET_MIN_OFF_SUCCESS_PCT" \
    --target-max-off-success-pct "$TARGET_MAX_OFF_SUCCESS_PCT" \
    --out "$OUT_DIR/frozen_summary.json" \
    --report-out "$OUT_DIR/frozen_summary.md"
  SUMMARY_REFRESH_RC=$?
  set -e
else
  python3 - "$OUT_DIR/frozen_summary.json" "$BASELINE_RECORD_COUNT" <<'PY'
import json
import sys
from pathlib import Path
summary_path = Path(sys.argv[1])
record_count = int(sys.argv[2])
summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
reasons = summary.get("reasons") if isinstance(summary.get("reasons"), list) else []
if "baseline_off_run_summary_missing" not in reasons:
    reasons.append("baseline_off_run_summary_missing")
summary["reasons"] = sorted(set([str(x) for x in reasons if str(x)]))
summary["status"] = "NEEDS_REVIEW" if summary.get("status") != "FAIL" else "FAIL"
summary["baseline_off_success_at_k_pct"] = None
summary["baseline_off_record_count"] = record_count
summary["baseline_execution_valid"] = record_count > 0
summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"status": summary.get("status"), "baseline_off_success_at_k_pct": None}))
PY
fi

python3 - "$OUT_DIR/frozen_summary.json" "$BASELINE_RC" <<'PY'
import json
import sys
from pathlib import Path
summary_path = Path(sys.argv[1])
baseline_rc = int(sys.argv[2])
summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
summary["baseline_off_run_exit_code"] = baseline_rc
summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"status": summary.get("status"), "baseline_off_success_at_k_pct": summary.get("baseline_off_success_at_k_pct")}))
PY

python3 - "$OUT_DIR/frozen_summary.json" "$SUMMARY_REFRESH_RC" <<'PY'
import json
import sys
from pathlib import Path
summary_path = Path(sys.argv[1])
summary_refresh_rc = int(sys.argv[2])
summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
summary["baseline_summary_refresh_exit_code"] = summary_refresh_rc
summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"status": summary.get("status"), "baseline_summary_refresh_exit_code": summary.get("baseline_summary_refresh_exit_code")}))
PY

python3 - "$OUT_DIR/frozen_summary.json" "$OUT_DIR/manifest.json" "$BASE_TASKSET" "$BASELINE_RUN_SUMMARY" "$BASELINE_RUN_RESULTS" "$BASELINE_PLANNER_BACKEND" "$BASELINE_LLM_MODEL" "$BACKEND" "$OM_DOCKER_IMAGE" "$LIVE_EXECUTOR_CMD" "$BASELINE_CMD_SHA256" "$LIVE_TIMEOUT_SEC" "$LIVE_MAX_OUTPUT_CHARS" "$MAX_ROUNDS" "$MAX_TIME_SEC" "$RUNTIME_THRESHOLD" "$GIT_COMMIT" <<'PY'
import json
import sys
from pathlib import Path

summary_path = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
base_taskset = str(sys.argv[3] or "")
baseline_run_summary = str(sys.argv[4] or "")
baseline_run_results = str(sys.argv[5] or "")
planner_backend = str(sys.argv[6] or "")
llm_model = str(sys.argv[7] or "")
backend = str(sys.argv[8] or "")
docker_image = str(sys.argv[9] or "")
live_executor_cmd = str(sys.argv[10] or "")
live_executor_cmd_sha256 = str(sys.argv[11] or "")
live_timeout_sec = int(float(sys.argv[12] or 0))
live_max_output_chars = int(float(sys.argv[13] or 0))
max_rounds = int(float(sys.argv[14] or 0))
max_time_sec = int(float(sys.argv[15] or 0))
runtime_threshold = float(sys.argv[16] or 0.0)
git_commit = str(sys.argv[17] or "")

baseline_provenance = {
    "taskset_in": base_taskset,
    "baseline_run_summary_path": baseline_run_summary,
    "baseline_run_results_path": baseline_run_results,
    "planner_backend": planner_backend,
    "llm_model": llm_model or None,
    "backend": backend,
    "docker_image": docker_image,
    "live_executor_cmd": live_executor_cmd,
    "live_executor_cmd_sha256": live_executor_cmd_sha256,
    "live_timeout_sec": live_timeout_sec,
    "live_max_output_chars": live_max_output_chars,
    "max_rounds": max_rounds,
    "max_time_sec": max_time_sec,
    "runtime_threshold": runtime_threshold,
    "git_commit": git_commit,
}

for path in (summary_path, manifest_path):
    if not path.exists():
        continue
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        continue
    payload["baseline_provenance"] = baseline_provenance
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

cat "$OUT_DIR/frozen_summary.json"

if [ "$ENFORCE_BASELINE_RANGE" = "1" ]; then
  python3 - "$OUT_DIR/frozen_summary.json" <<'PY'
import json
import sys
from pathlib import Path
summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if str(summary.get("status") or "") != "PASS":
    raise SystemExit(1)
PY
fi
