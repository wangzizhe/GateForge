#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L4_CLOSED_LOOP_OUT_DIR:-artifacts/agent_modelica_l4_closed_loop_v0}"
BASE_TASKSET="${GATEFORGE_AGENT_L4_CLOSED_LOOP_TASKSET:-assets_private/agent_modelica_l2_freeze_pack_v0/taskset_frozen.json}"
SCALES_RAW="${GATEFORGE_AGENT_L4_CLOSED_LOOP_SCALES:-small,medium}"

MAX_ROUNDS="${GATEFORGE_AGENT_L4_CLOSED_LOOP_MAX_ROUNDS:-2}"
MAX_TIME_SEC="${GATEFORGE_AGENT_L4_CLOSED_LOOP_MAX_TIME_SEC:-180}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_L4_CLOSED_LOOP_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_L4_CLOSED_LOOP_LIVE_TIMEOUT_SEC:-90}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_L4_CLOSED_LOOP_LIVE_MAX_OUTPUT_CHARS:-2400}"

L4_MAX_ROUNDS="${GATEFORGE_AGENT_L4_MAX_ROUNDS:-3}"
L4_POLICY_BACKEND="${GATEFORGE_AGENT_L4_POLICY_BACKEND:-rule}"
L4_MAX_ACTIONS_PER_ROUND="${GATEFORGE_AGENT_L4_MAX_ACTIONS_PER_ROUND:-3}"

MIN_SUCCESS_DELTA_PP="${GATEFORGE_AGENT_L4_MIN_SUCCESS_DELTA_PP:-5}"
MAX_REGRESSION_WORSEN_PP="${GATEFORGE_AGENT_L4_MAX_REGRESSION_WORSEN_PP:-2}"
MAX_PHYSICS_WORSEN_PP="${GATEFORGE_AGENT_L4_MAX_PHYSICS_WORSEN_PP:-2}"

LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_CLOSED_LOOP_LIVE_EXECUTOR_CMD:-python3 -m gateforge.agent_modelica_live_executor_gemini_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${GATEFORGE_AGENT_L4_CLOSED_LOOP_PLANNER_BACKEND:-rule}\" --backend \"${GATEFORGE_AGENT_L4_CLOSED_LOOP_BACKEND:-openmodelica_docker}\" --docker-image \"${GATEFORGE_AGENT_L4_CLOSED_LOOP_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}\"}"

REPAIR_MEMORY_PATH="${GATEFORGE_AGENT_REPAIR_MEMORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"
PATCH_TEMPLATE_ADAPTATIONS_PATH="${GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH:-data/private_failure_corpus/agent_modelica_patch_template_adaptations_v1.json}"
RETRIEVAL_POLICY_PATH="${GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH:-data/private_failure_corpus/agent_modelica_retrieval_policy_v1.json}"

if [ ! -f "$BASE_TASKSET" ]; then
  echo "Missing base taskset: $BASE_TASKSET" >&2
  exit 1
fi

mkdir -p "$OUT_DIR" "$OUT_DIR/off" "$OUT_DIR/on"
FILTERED_TASKSET="$OUT_DIR/taskset_filtered.json"

python3 - "$BASE_TASKSET" "$FILTERED_TASKSET" "$SCALES_RAW" <<'PY'
import json
import sys
from pathlib import Path

base_taskset_path = Path(sys.argv[1])
filtered_taskset_path = Path(sys.argv[2])
scales_raw = str(sys.argv[3] or "")
allowed_scales = {x.strip().lower() for x in scales_raw.split(",") if x.strip()}

payload = json.loads(base_taskset_path.read_text(encoding="utf-8"))
tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
filtered = []
for row in tasks:
    if not isinstance(row, dict):
        continue
    scale = str(row.get("scale") or "").strip().lower()
    if scale in allowed_scales:
        filtered.append(row)

filtered_payload = {
    "schema_version": str(payload.get("schema_version") or "agent_modelica_taskset_filtered_v0"),
    "generated_from": str(base_taskset_path),
    "allowed_scales": sorted(allowed_scales),
    "tasks": filtered,
}
filtered_taskset_path.write_text(json.dumps(filtered_payload, indent=2), encoding="utf-8")
print(
    json.dumps(
        {
            "status": "PASS" if filtered else "FAIL",
            "base_task_count": len(tasks),
            "filtered_task_count": len(filtered),
            "allowed_scales": sorted(allowed_scales),
        }
    )
)
if not filtered:
    raise SystemExit(1)
PY

run_once() {
  local run_tag="$1"
  local l4_flag="$2"
  local l4_args=()
  if [ "$l4_flag" = "on" ]; then
    l4_args+=(
      "--l4-enabled" "on"
      "--l4-max-rounds" "$L4_MAX_ROUNDS"
      "--l4-policy-backend" "$L4_POLICY_BACKEND"
      "--l4-max-actions-per-round" "$L4_MAX_ACTIONS_PER_ROUND"
    )
  else
    l4_args+=("--l4-enabled" "off")
  fi

  python3 -m gateforge.agent_modelica_run_contract_v1 \
    --taskset "$FILTERED_TASKSET" \
    --mode live \
    --max-rounds "$MAX_ROUNDS" \
    --max-time-sec "$MAX_TIME_SEC" \
    --runtime-threshold "$RUNTIME_THRESHOLD" \
    --repair-history "$REPAIR_MEMORY_PATH" \
    --patch-template-adaptations "$PATCH_TEMPLATE_ADAPTATIONS_PATH" \
    --retrieval-policy "$RETRIEVAL_POLICY_PATH" \
    --live-executor-cmd "$LIVE_EXECUTOR_CMD" \
    --live-timeout-sec "$LIVE_TIMEOUT_SEC" \
    --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS" \
    "${l4_args[@]}" \
    --results-out "$OUT_DIR/$run_tag/run_results.json" \
    --out "$OUT_DIR/$run_tag/run_summary.json"
}

run_once off off
run_once on on

python3 - "$OUT_DIR" "$FILTERED_TASKSET" "$MIN_SUCCESS_DELTA_PP" "$MAX_REGRESSION_WORSEN_PP" "$MAX_PHYSICS_WORSEN_PP" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out_dir = Path(sys.argv[1])
filtered_taskset = Path(sys.argv[2])
min_success_delta_pp = float(sys.argv[3])
max_regression_worsen_pp = float(sys.argv[4])
max_physics_worsen_pp = float(sys.argv[5])

def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def _infra_reason(stderr: str, reason: str, log_excerpt: str) -> str:
    text = " ".join([str(stderr or ""), str(reason or ""), str(log_excerpt or "")]).lower()
    if "timeoutexpired" in text or "timed out" in text or "live_executor_timeout" in text:
        return "timeout"
    if "permission denied while trying to connect to the docker api" in text:
        return "docker_permission_denied"
    if "includes invalid characters for a local volume name" in text:
        return "docker_volume_mount_invalid"
    if "failed to load package modelica" in text:
        return "msl_load_failed"
    if "model_path_missing" in text or "no such file or directory" in text:
        return "path_not_found"
    if "mount" in text and "permission denied" in text:
        return "mount_permission_denied"
    return ""

def _pct(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round((num / den) * 100.0, 2)

def _summarize_run(run_dir: Path) -> dict:
    run_summary = _load(run_dir / "run_summary.json")
    run_results = _load(run_dir / "run_results.json")
    records = run_results.get("records") if isinstance(run_results.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]
    record_count = len(records)
    regression_fail_count = len([x for x in records if not bool((x.get("hard_checks") or {}).get("regression_pass"))])
    physics_fail_count = len([x for x in records if not bool((x.get("hard_checks") or {}).get("physics_contract_pass"))])
    attempts = 0
    infra_count = 0
    infra_by_reason: dict[str, int] = {}
    for rec in records:
        rows = rec.get("attempts") if isinstance(rec.get("attempts"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            attempts += 1
            infra = _infra_reason(
                stderr=row.get("stderr_snippet"),
                reason=row.get("reason"),
                log_excerpt=row.get("log_excerpt"),
            )
            if infra:
                infra_count += 1
                infra_by_reason[infra] = int(infra_by_reason.get(infra, 0)) + 1
    return {
        "run_contract_status": str(run_summary.get("status") or ""),
        "success_at_k_pct": float(run_summary.get("success_at_k_pct") or 0.0),
        "record_count": record_count,
        "attempt_count": attempts,
        "regression_fail_rate_pct": _pct(regression_fail_count, record_count),
        "physics_fail_rate_pct": _pct(physics_fail_count, record_count),
        "infra_failure_count": infra_count,
        "infra_failure_by_reason": {k: infra_by_reason[k] for k in sorted(infra_by_reason.keys())},
    }

taskset_payload = _load(filtered_taskset)
filtered_tasks = taskset_payload.get("tasks") if isinstance(taskset_payload.get("tasks"), list) else []
filtered_task_count = len([x for x in filtered_tasks if isinstance(x, dict)])

off = _summarize_run(out_dir / "off")
on = _summarize_run(out_dir / "on")
delta_success = round(float(on["success_at_k_pct"]) - float(off["success_at_k_pct"]), 2)
delta_regression_fail_rate = round(float(on["regression_fail_rate_pct"]) - float(off["regression_fail_rate_pct"]), 2)
delta_physics_fail_rate = round(float(on["physics_fail_rate_pct"]) - float(off["physics_fail_rate_pct"]), 2)

reasons: list[str] = []
if filtered_task_count <= 0:
    reasons.append("filtered_taskset_empty")
if int(off["attempt_count"]) <= 0:
    reasons.append("off_attempts_missing")
if int(on["attempt_count"]) <= 0:
    reasons.append("on_attempts_missing")
if int(off["infra_failure_count"]) > 0:
    reasons.append("off_infra_failure_present")
if int(on["infra_failure_count"]) > 0:
    reasons.append("on_infra_failure_present")
if delta_success < float(min_success_delta_pp):
    reasons.append("success_delta_below_threshold")
if delta_regression_fail_rate > float(max_regression_worsen_pp):
    reasons.append("regression_fail_rate_worse_than_threshold")
if delta_physics_fail_rate > float(max_physics_worsen_pp):
    reasons.append("physics_fail_rate_worse_than_threshold")

status = "PASS" if not reasons else "FAIL"
summary = {
    "schema_version": "agent_modelica_l4_closed_loop_v0",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "filtered_task_count": filtered_task_count,
    "off": off,
    "on": on,
    "delta": {
        "success_at_k_pp": delta_success,
        "regression_fail_rate_pp": delta_regression_fail_rate,
        "physics_fail_rate_pp": delta_physics_fail_rate,
    },
    "acceptance": {
        "min_success_delta_pp": min_success_delta_pp,
        "max_regression_worsen_pp": max_regression_worsen_pp,
        "max_physics_worsen_pp": max_physics_worsen_pp,
        "infra_failure_count_must_equal": 0,
    },
    "reasons": reasons,
    "paths": {
        "filtered_taskset": str(filtered_taskset),
        "off_results": str(out_dir / "off" / "run_results.json"),
        "off_summary": str(out_dir / "off" / "run_summary.json"),
        "on_results": str(out_dir / "on" / "run_results.json"),
        "on_summary": str(out_dir / "on" / "run_summary.json"),
    },
}
(out_dir / "ab_compare_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out_dir / "l4_closed_loop_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out_dir / "l4_closed_loop_summary.md").write_text(
    "\n".join(
        [
            "# Agent Modelica L4 Closed Loop v0",
            "",
            f"- status: `{status}`",
            f"- filtered_task_count: `{filtered_task_count}`",
            f"- off success_at_k_pct: `{off['success_at_k_pct']}`",
            f"- on success_at_k_pct: `{on['success_at_k_pct']}`",
            f"- delta success_at_k_pp: `{delta_success}`",
            f"- delta regression_fail_rate_pp: `{delta_regression_fail_rate}`",
            f"- delta physics_fail_rate_pp: `{delta_physics_fail_rate}`",
            f"- off infra_failure_count: `{off['infra_failure_count']}`",
            f"- on infra_failure_count: `{on['infra_failure_count']}`",
            f"- reasons: `{reasons}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(
    json.dumps(
        {
            "status": status,
            "delta_success_at_k_pp": delta_success,
            "off_success_at_k_pct": off["success_at_k_pct"],
            "on_success_at_k_pct": on["success_at_k_pct"],
        }
    )
)
if status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/ab_compare_summary.json"
