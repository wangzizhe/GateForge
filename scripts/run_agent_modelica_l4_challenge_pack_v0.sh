#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L4_CHALLENGE_OUT_DIR:-assets_private/agent_modelica_l4_challenge_pack_v0}"
BASE_TASKSET="${GATEFORGE_AGENT_L4_CHALLENGE_BASE_TASKSET:-assets_private/agent_modelica_l2_freeze_pack_v0/taskset_frozen.json}"
SCALES="${GATEFORGE_AGENT_L4_CHALLENGE_SCALES:-small,medium}"
FAILURE_TYPES="${GATEFORGE_AGENT_L4_CHALLENGE_FAILURE_TYPES:-model_check_error,simulate_error,semantic_regression}"
PER_FAILURE_TYPE_CAP="${GATEFORGE_AGENT_L4_CHALLENGE_PER_FAILURE_TYPE_CAP:-6}"
SPLIT_SEED="${GATEFORGE_AGENT_L4_CHALLENGE_SPLIT_SEED:-agent_modelica_l4_challenge_v0}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_L4_CHALLENGE_HOLDOUT_RATIO:-0.15}"
TARGET_MIN_OFF_SUCCESS_PCT="${GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MIN_OFF_SUCCESS_PCT:-60}"
TARGET_MAX_OFF_SUCCESS_PCT="${GATEFORGE_AGENT_L4_CHALLENGE_TARGET_MAX_OFF_SUCCESS_PCT:-90}"
ENFORCE_BASELINE_RANGE="${GATEFORGE_AGENT_L4_CHALLENGE_ENFORCE_BASELINE_RANGE:-1}"

PLANNER_BACKEND="${GATEFORGE_AGENT_L4_CHALLENGE_PLANNER_BACKEND:-rule}"
BACKEND="${GATEFORGE_AGENT_L4_CHALLENGE_BACKEND:-openmodelica_docker}"
OM_DOCKER_IMAGE="${GATEFORGE_AGENT_L4_CHALLENGE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"
MAX_ROUNDS="${GATEFORGE_AGENT_L4_CHALLENGE_MAX_ROUNDS:-1}"
MAX_TIME_SEC="${GATEFORGE_AGENT_L4_CHALLENGE_MAX_TIME_SEC:-120}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_L4_CHALLENGE_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_L4_CHALLENGE_LIVE_TIMEOUT_SEC:-90}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_L4_CHALLENGE_LIVE_MAX_OUTPUT_CHARS:-1600}"
LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_CHALLENGE_LIVE_EXECUTOR_CMD:-python3 -m gateforge.agent_modelica_live_executor_gemini_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${PLANNER_BACKEND}\" --backend \"${BACKEND}\" --docker-image \"${OM_DOCKER_IMAGE}\"}"

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
  --per-failure-type-cap "$PER_FAILURE_TYPE_CAP" \
  --holdout-ratio "$HOLDOUT_RATIO" \
  --split-seed "$SPLIT_SEED" \
  --target-min-off-success-pct "$TARGET_MIN_OFF_SUCCESS_PCT" \
  --target-max-off-success-pct "$TARGET_MAX_OFF_SUCCESS_PCT" \
  --out "$OUT_DIR/frozen_summary.json" \
  --report-out "$OUT_DIR/frozen_summary.md"

set +e
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
  --results-out "$OUT_DIR/baseline_off_run_results.json" \
  --out "$OUT_DIR/baseline_off_run_summary.json"
BASELINE_RC=$?
set -e

BASELINE_OFF_SUCCESS=""
if [ -f "$OUT_DIR/baseline_off_run_summary.json" ]; then
  BASELINE_OFF_SUCCESS="$(python3 - "$OUT_DIR/baseline_off_run_summary.json" <<'PY'
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

if [ -n "$BASELINE_OFF_SUCCESS" ]; then
  python3 -m gateforge.agent_modelica_l4_challenge_pack_v0 \
    --taskset-in "$BASE_TASKSET" \
    --out-dir "$OUT_DIR" \
    --scales "$SCALES" \
    --failure-types "$FAILURE_TYPES" \
    --per-failure-type-cap "$PER_FAILURE_TYPE_CAP" \
    --holdout-ratio "$HOLDOUT_RATIO" \
    --split-seed "$SPLIT_SEED" \
    --baseline-off-success-at-k-pct "$BASELINE_OFF_SUCCESS" \
    --target-min-off-success-pct "$TARGET_MIN_OFF_SUCCESS_PCT" \
    --target-max-off-success-pct "$TARGET_MAX_OFF_SUCCESS_PCT" \
    --out "$OUT_DIR/frozen_summary.json" \
    --report-out "$OUT_DIR/frozen_summary.md"
else
  python3 - "$OUT_DIR/frozen_summary.json" <<'PY'
import json
import sys
from pathlib import Path
summary_path = Path(sys.argv[1])
summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
reasons = summary.get("reasons") if isinstance(summary.get("reasons"), list) else []
if "baseline_off_run_summary_missing" not in reasons:
    reasons.append("baseline_off_run_summary_missing")
summary["reasons"] = sorted(set([str(x) for x in reasons if str(x)]))
summary["status"] = "NEEDS_REVIEW" if summary.get("status") != "FAIL" else "FAIL"
summary["baseline_off_success_at_k_pct"] = None
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
