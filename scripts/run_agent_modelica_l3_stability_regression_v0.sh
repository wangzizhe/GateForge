#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L3_STABILITY_OUT_DIR:-artifacts/agent_modelica_l3_stability_regression_v0}"
BASE_TASKSET="${GATEFORGE_AGENT_L3_STABILITY_TASKSET:-assets_private/agent_modelica_l2_freeze_pack_v0/taskset_frozen.json}"
SCALES_RAW="${GATEFORGE_AGENT_L3_STABILITY_SCALES:-small,medium}"

MAX_ROUNDS="${GATEFORGE_AGENT_L3_STABILITY_MAX_ROUNDS:-2}"
MAX_TIME_SEC="${GATEFORGE_AGENT_L3_STABILITY_MAX_TIME_SEC:-180}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_L3_STABILITY_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_L3_STABILITY_LIVE_TIMEOUT_SEC:-90}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_L3_STABILITY_LIVE_MAX_OUTPUT_CHARS:-2400}"
L3_LOW_CONFIDENCE_THRESHOLD="${GATEFORGE_AGENT_L3_LOW_CONFIDENCE_THRESHOLD:-0.65}"
L3_MIN_PARSE_COVERAGE_PCT="${GATEFORGE_AGENT_L3_MIN_PARSE_COVERAGE_PCT:-95}"
L3_MIN_TYPE_MATCH_RATE_PCT="${GATEFORGE_AGENT_L3_MIN_TYPE_MATCH_RATE_PCT:-70}"
L3_MIN_STAGE_MATCH_RATE_PCT="${GATEFORGE_AGENT_L3_MIN_STAGE_MATCH_RATE_PCT:-70}"
L3_MAX_LOW_CONFIDENCE_RATE_PCT="${GATEFORGE_AGENT_L3_MAX_LOW_CONFIDENCE_RATE_PCT:-30}"

LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_L3_STABILITY_LIVE_EXECUTOR_CMD:-python3 -m gateforge.agent_modelica_live_executor_gemini_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${GATEFORGE_AGENT_L3_STABILITY_PLANNER_BACKEND:-rule}\" --backend \"${GATEFORGE_AGENT_L3_STABILITY_BACKEND:-openmodelica_docker}\" --docker-image \"${GATEFORGE_AGENT_L3_STABILITY_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}\"}"

REPAIR_MEMORY_PATH="${GATEFORGE_AGENT_REPAIR_MEMORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"
PATCH_TEMPLATE_ADAPTATIONS_PATH="${GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH:-data/private_failure_corpus/agent_modelica_patch_template_adaptations_v1.json}"
RETRIEVAL_POLICY_PATH="${GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH:-data/private_failure_corpus/agent_modelica_retrieval_policy_v1.json}"

if [ ! -f "$BASE_TASKSET" ]; then
  echo "Missing base taskset: $BASE_TASKSET" >&2
  exit 1
fi

mkdir -p "$OUT_DIR" "$OUT_DIR/run1" "$OUT_DIR/run2"
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
    --results-out "$OUT_DIR/$run_tag/run_results.json" \
    --out "$OUT_DIR/$run_tag/run_summary.json"

  set +e
  python3 -m gateforge.agent_modelica_diagnostic_quality_v0 \
    --run-results "$OUT_DIR/$run_tag/run_results.json" \
    --taskset "$FILTERED_TASKSET" \
    --low-confidence-threshold "$L3_LOW_CONFIDENCE_THRESHOLD" \
    --out "$OUT_DIR/$run_tag/diagnostic_quality_summary.json" \
    --report-out "$OUT_DIR/$run_tag/diagnostic_quality_summary.md"
  local quality_rc=$?
  set -e
  echo "$quality_rc" > "$OUT_DIR/$run_tag/diagnostic_quality.exit_code"

  set +e
  python3 -m gateforge.agent_modelica_l3_diagnostic_gate_v0 \
    --diagnostic-quality-summary "$OUT_DIR/$run_tag/diagnostic_quality_summary.json" \
    --min-parse-coverage-pct "$L3_MIN_PARSE_COVERAGE_PCT" \
    --min-canonical-type-match-rate-pct "$L3_MIN_TYPE_MATCH_RATE_PCT" \
    --min-stage-match-rate-pct "$L3_MIN_STAGE_MATCH_RATE_PCT" \
    --max-low-confidence-rate-pct "$L3_MAX_LOW_CONFIDENCE_RATE_PCT" \
    --out "$OUT_DIR/$run_tag/l3_diagnostic_gate_summary.json" \
    --report-out "$OUT_DIR/$run_tag/l3_diagnostic_gate_summary.md"
  local gate_rc=$?
  set -e
  echo "$gate_rc" > "$OUT_DIR/$run_tag/l3_diagnostic_gate.exit_code"
}

run_once run1
run_once run2

python3 - "$OUT_DIR" "$FILTERED_TASKSET" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out_dir = Path(sys.argv[1])
filtered_taskset = Path(sys.argv[2])

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

def _summarize_run(run_dir: Path) -> dict:
    run_summary = _load(run_dir / "run_summary.json")
    run_results = _load(run_dir / "run_results.json")
    quality = _load(run_dir / "diagnostic_quality_summary.json")
    gate = _load(run_dir / "l3_diagnostic_gate_summary.json")

    records = run_results.get("records") if isinstance(run_results.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]

    infra_count = 0
    infra_by_reason: dict[str, int] = {}
    attempt_count = 0
    for rec in records:
        attempts = rec.get("attempts") if isinstance(rec.get("attempts"), list) else []
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            attempt_count += 1
            infra = _infra_reason(
                stderr=attempt.get("stderr_snippet"),
                reason=attempt.get("reason"),
                log_excerpt=attempt.get("log_excerpt"),
            )
            if infra:
                infra_count += 1
                infra_by_reason[infra] = int(infra_by_reason.get(infra, 0)) + 1

    return {
        "run_contract_status": str(run_summary.get("status") or ""),
        "success_at_k_pct": float(run_summary.get("success_at_k_pct") or 0.0),
        "records_count": int(run_summary.get("records_count") or 0),
        "attempt_count": int(attempt_count),
        "l3_gate_status": str(gate.get("status") or ""),
        "l3_gate_result": str(gate.get("gate_result") or ""),
        "l3_parse_coverage_pct": float(quality.get("parse_coverage_pct") or 0.0),
        "l3_type_match_rate_pct": float(
            quality.get("canonical_type_match_rate_pct") or quality.get("type_match_rate_pct") or 0.0
        ),
        "l3_stage_match_rate_pct": float(quality.get("stage_match_rate_pct") or 0.0),
        "l3_low_confidence_rate_pct": float(quality.get("low_confidence_rate_pct") or 0.0),
        "infra_failure_count": int(infra_count),
        "infra_failure_by_reason": {k: infra_by_reason[k] for k in sorted(infra_by_reason.keys())},
    }

taskset_payload = _load(filtered_taskset)
filtered_tasks = taskset_payload.get("tasks") if isinstance(taskset_payload.get("tasks"), list) else []
filtered_task_count = len([x for x in filtered_tasks if isinstance(x, dict)])

run1 = _summarize_run(out_dir / "run1")
run2 = _summarize_run(out_dir / "run2")
reasons: list[str] = []

for idx, row in enumerate([run1, run2], start=1):
    if row["attempt_count"] <= 0:
        reasons.append(f"run{idx}_attempts_missing")
    if row["l3_gate_status"] != "PASS":
        reasons.append(f"run{idx}_l3_gate_not_pass")
    if row["infra_failure_count"] > 0:
        reasons.append(f"run{idx}_infra_failure_present")

status = "PASS" if (filtered_task_count > 0 and not reasons) else "FAIL"
if filtered_task_count <= 0:
    reasons.append("filtered_taskset_empty")
    status = "FAIL"

summary = {
    "schema_version": "agent_modelica_l3_stability_regression_v0",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "filtered_task_count": filtered_task_count,
    "run1": run1,
    "run2": run2,
    "acceptance": {
        "run_gate_status_must_equal": "PASS",
        "run_infra_failure_count_must_equal": 0,
        "attempt_count_must_be_positive": True,
    },
    "reasons": reasons,
    "paths": {
        "filtered_taskset": str(filtered_taskset),
        "run1_results": str(out_dir / "run1" / "run_results.json"),
        "run1_quality": str(out_dir / "run1" / "diagnostic_quality_summary.json"),
        "run1_gate": str(out_dir / "run1" / "l3_diagnostic_gate_summary.json"),
        "run2_results": str(out_dir / "run2" / "run_results.json"),
        "run2_quality": str(out_dir / "run2" / "diagnostic_quality_summary.json"),
        "run2_gate": str(out_dir / "run2" / "l3_diagnostic_gate_summary.json"),
    },
}

(out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out_dir / "summary.md").write_text(
    "\n".join(
        [
            "# Agent Modelica L3 Stability Regression v0",
            "",
            f"- status: `{status}`",
            f"- filtered_task_count: `{filtered_task_count}`",
            f"- run1 l3_gate_status: `{run1['l3_gate_status']}`",
            f"- run2 l3_gate_status: `{run2['l3_gate_status']}`",
            f"- run1 parse/type/stage: `{run1['l3_parse_coverage_pct']}/{run1['l3_type_match_rate_pct']}/{run1['l3_stage_match_rate_pct']}`",
            f"- run2 parse/type/stage: `{run2['l3_parse_coverage_pct']}/{run2['l3_type_match_rate_pct']}/{run2['l3_stage_match_rate_pct']}`",
            f"- run1 infra_failure_count: `{run1['infra_failure_count']}`",
            f"- run2 infra_failure_count: `{run2['infra_failure_count']}`",
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
            "filtered_task_count": filtered_task_count,
            "run1_gate_status": run1["l3_gate_status"],
            "run2_gate_status": run2["l3_gate_status"],
        }
    )
)
if status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
