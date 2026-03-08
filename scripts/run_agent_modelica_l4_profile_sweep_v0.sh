#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_OUT_DIR:-artifacts/agent_modelica_l4_profile_sweep_v0}"
DEFAULT_BASE_TASKSET="assets_private/agent_modelica_l4_challenge_pack_v0/taskset_frozen.json"
if [ ! -f "$DEFAULT_BASE_TASKSET" ]; then
  DEFAULT_BASE_TASKSET="assets_private/agent_modelica_l2_freeze_pack_v0/taskset_frozen.json"
fi
BASE_TASKSET="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_TASKSET:-$DEFAULT_BASE_TASKSET}"
SCALES_RAW="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_SCALES:-small,medium}"
PROFILES_RAW="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_PROFILES:-score_v1,score_v1a,score_v1b,score_v1c}"
ENFORCE_PASS="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_ENFORCE_PASS:-0}"

PLANNER_BACKEND="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_PLANNER_BACKEND:-rule}"
BACKEND="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_BACKEND:-openmodelica_docker}"
OM_DOCKER_IMAGE="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"

MAX_ROUNDS="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_ROUNDS:-2}"
MAX_TIME_SEC="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_TIME_SEC:-180}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_TIMEOUT_SEC:-90}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_MAX_OUTPUT_CHARS:-2400}"

L4_MAX_ROUNDS="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_MAX_ROUNDS:-3}"
L4_POLICY_BACKEND="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_POLICY_BACKEND:-rule}"
L4_LLM_FALLBACK_THRESHOLD="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_LLM_FALLBACK_THRESHOLD:-2}"
L4_MAX_ACTIONS_PER_ROUND="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_L4_MAX_ACTIONS_PER_ROUND:-3}"

MIN_SUCCESS_DELTA_PP="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_MIN_SUCCESS_DELTA_PP:-5}"
MAX_REGRESSION_WORSEN_PP="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_REGRESSION_WORSEN_PP:-2}"
MAX_PHYSICS_WORSEN_PP="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_MAX_PHYSICS_WORSEN_PP:-2}"

LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_PROFILE_SWEEP_LIVE_EXECUTOR_CMD:-python3 -m gateforge.agent_modelica_live_executor_gemini_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${PLANNER_BACKEND}\" --backend \"${BACKEND}\" --docker-image \"${OM_DOCKER_IMAGE}\"}"

if [ ! -f "$BASE_TASKSET" ]; then
  echo "Missing base taskset: $BASE_TASKSET" >&2
  exit 1
fi

mkdir -p "$OUT_DIR/profiles"
PROFILE_RC_ROWS_JSON="$OUT_DIR/profile_rc_rows.json"
printf '[]' > "$PROFILE_RC_ROWS_JSON"

IFS=',' read -r -a _profiles <<< "$PROFILES_RAW"
profiles=()
for raw in "${_profiles[@]}"; do
  p="$(echo "$raw" | xargs)"
  if [ -n "$p" ]; then
    profiles+=("$p")
  fi
done
if [ "${#profiles[@]}" -eq 0 ]; then
  echo "No profiles provided via GATEFORGE_AGENT_L4_PROFILE_SWEEP_PROFILES" >&2
  exit 1
fi

for profile in "${profiles[@]}"; do
  profile_out="$OUT_DIR/profiles/$profile"
  mkdir -p "$profile_out"
  set +e
  GATEFORGE_AGENT_L4_CLOSED_LOOP_OUT_DIR="$profile_out" \
  GATEFORGE_AGENT_L4_CLOSED_LOOP_TASKSET="$BASE_TASKSET" \
  GATEFORGE_AGENT_L4_CLOSED_LOOP_SCALES="$SCALES_RAW" \
  GATEFORGE_AGENT_L4_CLOSED_LOOP_PLANNER_BACKEND="$PLANNER_BACKEND" \
  GATEFORGE_AGENT_L4_CLOSED_LOOP_BACKEND="$BACKEND" \
  GATEFORGE_AGENT_L4_CLOSED_LOOP_OM_DOCKER_IMAGE="$OM_DOCKER_IMAGE" \
  GATEFORGE_AGENT_L4_CLOSED_LOOP_MAX_ROUNDS="$MAX_ROUNDS" \
  GATEFORGE_AGENT_L4_CLOSED_LOOP_MAX_TIME_SEC="$MAX_TIME_SEC" \
  GATEFORGE_AGENT_L4_CLOSED_LOOP_RUNTIME_THRESHOLD="$RUNTIME_THRESHOLD" \
  GATEFORGE_AGENT_L4_CLOSED_LOOP_LIVE_TIMEOUT_SEC="$LIVE_TIMEOUT_SEC" \
  GATEFORGE_AGENT_L4_CLOSED_LOOP_LIVE_MAX_OUTPUT_CHARS="$LIVE_MAX_OUTPUT_CHARS" \
  GATEFORGE_AGENT_L4_CLOSED_LOOP_LIVE_EXECUTOR_CMD="$LIVE_EXECUTOR_CMD" \
  GATEFORGE_AGENT_L4_MAX_ROUNDS="$L4_MAX_ROUNDS" \
  GATEFORGE_AGENT_L4_POLICY_BACKEND="$L4_POLICY_BACKEND" \
  GATEFORGE_AGENT_L4_POLICY_PROFILE="$profile" \
  GATEFORGE_AGENT_L4_LLM_FALLBACK_THRESHOLD="$L4_LLM_FALLBACK_THRESHOLD" \
  GATEFORGE_AGENT_L4_MAX_ACTIONS_PER_ROUND="$L4_MAX_ACTIONS_PER_ROUND" \
  GATEFORGE_AGENT_L4_MIN_SUCCESS_DELTA_PP="$MIN_SUCCESS_DELTA_PP" \
  GATEFORGE_AGENT_L4_MAX_REGRESSION_WORSEN_PP="$MAX_REGRESSION_WORSEN_PP" \
  GATEFORGE_AGENT_L4_MAX_PHYSICS_WORSEN_PP="$MAX_PHYSICS_WORSEN_PP" \
  bash scripts/run_agent_modelica_l4_closed_loop_v0.sh
  rc=$?
  set -e
  python3 - "$PROFILE_RC_ROWS_JSON" "$profile" "$rc" "$profile_out" <<'PY'
import json
import sys
from pathlib import Path

rows_path = Path(sys.argv[1])
profile = str(sys.argv[2] or "").strip()
rc = int(sys.argv[3])
profile_out = Path(sys.argv[4])
rows = json.loads(rows_path.read_text(encoding="utf-8")) if rows_path.exists() else []
if not isinstance(rows, list):
    rows = []
rows.append(
    {
        "profile": profile,
        "exit_code": rc,
        "ab_compare_summary_path": str(profile_out / "ab_compare_summary.json"),
    }
)
rows_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
print(json.dumps({"profile": profile, "exit_code": rc}))
PY
done

python3 - "$OUT_DIR" "$BASE_TASKSET" "$SCALES_RAW" "$PROFILES_RAW" "$PROFILE_RC_ROWS_JSON" "$PLANNER_BACKEND" "$BACKEND" "$L4_POLICY_BACKEND" "$MIN_SUCCESS_DELTA_PP" "$MAX_REGRESSION_WORSEN_PP" "$MAX_PHYSICS_WORSEN_PP" "$ENFORCE_PASS" <<'PY'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out_dir = Path(sys.argv[1])
base_taskset = Path(sys.argv[2])
scales_raw = str(sys.argv[3] or "")
profiles_raw = str(sys.argv[4] or "")
rows_path = Path(sys.argv[5])
planner_backend = str(sys.argv[6] or "")
backend = str(sys.argv[7] or "")
l4_policy_backend = str(sys.argv[8] or "")
min_success_delta_pp = float(sys.argv[9])
max_regression_worsen_pp = float(sys.argv[10])
max_physics_worsen_pp = float(sys.argv[11])
enforce_pass = str(sys.argv[12]).strip() == "1"

profile_rows = json.loads(rows_path.read_text(encoding="utf-8")) if rows_path.exists() else []
profile_rows = [x for x in profile_rows if isinstance(x, dict)]

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}

results = []
for row in profile_rows:
    profile = str(row.get("profile") or "").strip()
    exit_code = int(row.get("exit_code") or 0)
    summary_path = Path(str(row.get("ab_compare_summary_path") or ""))
    payload = _load_json(summary_path)
    on = payload.get("on") if isinstance(payload.get("on"), dict) else {}
    off = payload.get("off") if isinstance(payload.get("off"), dict) else {}
    delta = payload.get("delta") if isinstance(payload.get("delta"), dict) else {}
    reasons = [str(x) for x in (payload.get("reasons") or []) if isinstance(x, str)]
    status = str(payload.get("status") or ("PASS" if exit_code == 0 else "FAIL"))
    results.append(
        {
            "profile": profile,
            "status": status,
            "exit_code": exit_code,
            "success_at_k_pct_on": float(on.get("success_at_k_pct") or 0.0),
            "success_at_k_pct_off": float(off.get("success_at_k_pct") or 0.0),
            "delta_success_at_k_pp": float(delta.get("success_at_k_pp") or 0.0),
            "delta_regression_fail_rate_pp": float(delta.get("regression_fail_rate_pp") or 0.0),
            "delta_physics_fail_rate_pp": float(delta.get("physics_fail_rate_pp") or 0.0),
            "infra_failure_count_on": int(on.get("infra_failure_count") or 0),
            "no_progress_rate_pct_on": float(on.get("no_progress_rate_pct") or 0.0),
            "llm_fallback_rate_pct_on": float(on.get("llm_fallback_rate_pct") or 0.0),
            "l4_primary_reason_on": str(on.get("l4_primary_reason") or "none"),
            "reason_distribution_on": on.get("reason_distribution") if isinstance(on.get("reason_distribution"), dict) else {},
            "reasons": reasons,
            "path": str(summary_path),
        }
    )

results.sort(
    key=lambda x: (
        str(x.get("profile") or ""),
    )
)
pass_rows = [x for x in results if str(x.get("status") or "") == "PASS"]
best = None
if pass_rows:
    best = sorted(
        pass_rows,
        key=lambda x: (
            -float(x.get("delta_success_at_k_pp") or 0.0),
            -float(x.get("success_at_k_pct_on") or 0.0),
            float(x.get("no_progress_rate_pct_on") or 0.0),
            float(x.get("llm_fallback_rate_pct_on") or 0.0),
            str(x.get("profile") or ""),
        ),
    )[0]

status = "PASS" if best else "FAIL"
summary = {
    "schema_version": "agent_modelica_l4_profile_sweep_v0",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "planner_backend": planner_backend,
    "backend": backend,
    "l4_policy_backend": l4_policy_backend,
    "base_taskset": str(base_taskset),
    "base_taskset_sha256": hashlib.sha256(base_taskset.read_bytes()).hexdigest() if base_taskset.exists() else "",
    "scales": [x.strip() for x in scales_raw.split(",") if x.strip()],
    "profiles": [x.strip() for x in profiles_raw.split(",") if x.strip()],
    "acceptance": {
        "min_success_delta_pp": min_success_delta_pp,
        "max_regression_worsen_pp": max_regression_worsen_pp,
        "max_physics_worsen_pp": max_physics_worsen_pp,
        "infra_failure_count_must_equal": 0,
    },
    "profile_results": results,
    "recommended_profile": str(best.get("profile") or "") if isinstance(best, dict) else "",
    "recommended_profile_result": best if isinstance(best, dict) else {},
    "reasons": [] if best else ["no_profile_passed"],
}

(out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out_dir / "summary.md").write_text(
    "\n".join(
        [
            "# Agent Modelica L4 Profile Sweep v0",
            "",
            f"- status: `{summary.get('status')}`",
            f"- planner_backend: `{summary.get('planner_backend')}`",
            f"- backend: `{summary.get('backend')}`",
            f"- l4_policy_backend: `{summary.get('l4_policy_backend')}`",
            f"- recommended_profile: `{summary.get('recommended_profile')}`",
            f"- profile_count: `{len(results)}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(
    json.dumps(
        {
            "status": summary.get("status"),
            "recommended_profile": summary.get("recommended_profile"),
            "profile_count": len(results),
        }
    )
)
if enforce_pass and summary.get("status") != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
