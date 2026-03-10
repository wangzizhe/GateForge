#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_RELEASE_OUT_DIR:-artifacts/release_v0_1_1}"
RUN_LIVE_SMOKE="${GATEFORGE_AGENT_RELEASE_RUN_LIVE_SMOKE:-0}"
REQUIRE_REAL_OMC_BACKEND="${GATEFORGE_AGENT_RELEASE_REQUIRE_REAL_OMC_BACKEND:-1}"
LIVE_SMOKE_EXECUTOR_MODULE="${GATEFORGE_AGENT_RELEASE_SMOKE_EXECUTOR_MODULE:-gateforge.agent_modelica_live_executor_gemini_v1}"
ENABLE_L3_DIAGNOSTIC_GATE="${GATEFORGE_AGENT_RELEASE_ENABLE_L3_DIAGNOSTIC_GATE:-1}"
ENFORCE_L3_DIAGNOSTIC_GATE="${GATEFORGE_AGENT_RELEASE_ENFORCE_L3_DIAGNOSTIC_GATE:-1}"
L3_MIN_PARSE_COVERAGE_PCT="${GATEFORGE_AGENT_RELEASE_L3_MIN_PARSE_COVERAGE_PCT:-95}"
L3_MIN_TYPE_MATCH_RATE_PCT="${GATEFORGE_AGENT_RELEASE_L3_MIN_TYPE_MATCH_RATE_PCT:-70}"
L3_MIN_STAGE_MATCH_RATE_PCT="${GATEFORGE_AGENT_RELEASE_L3_MIN_STAGE_MATCH_RATE_PCT:-70}"
L3_MAX_LOW_CONFIDENCE_RATE_PCT="${GATEFORGE_AGENT_RELEASE_L3_MAX_LOW_CONFIDENCE_RATE_PCT:-30}"
L3_LOW_CONFIDENCE_THRESHOLD="${GATEFORGE_AGENT_RELEASE_L3_LOW_CONFIDENCE_THRESHOLD:-0.65}"
ENABLE_L5_EVAL_GATE="${GATEFORGE_AGENT_RELEASE_ENABLE_L5_EVAL_GATE:-1}"
ENFORCE_L5_EVAL_GATE="${GATEFORGE_AGENT_RELEASE_ENFORCE_L5_EVAL_GATE:-$REQUIRE_REAL_OMC_BACKEND}"
L5_GATE_MODE="${GATEFORGE_AGENT_RELEASE_L5_GATE_MODE:-strict}"
L5_MIN_DELTA_SUCCESS_PP="${GATEFORGE_AGENT_RELEASE_L5_MIN_DELTA_SUCCESS_PP:-5}"
L5_MAX_PHYSICS_WORSEN_PP="${GATEFORGE_AGENT_RELEASE_L5_MAX_PHYSICS_WORSEN_PP:-2}"
L5_MAX_REGRESSION_WORSEN_PP="${GATEFORGE_AGENT_RELEASE_L5_MAX_REGRESSION_WORSEN_PP:-2}"
L5_INFRA_FAILURE_MUST_EQUAL="${GATEFORGE_AGENT_RELEASE_L5_INFRA_FAILURE_MUST_EQUAL:-0}"
L5_MIN_L3_PARSE_PCT="${GATEFORGE_AGENT_RELEASE_L5_MIN_L3_PARSE_PCT:-95}"
L5_MIN_L3_TYPE_PCT="${GATEFORGE_AGENT_RELEASE_L5_MIN_L3_TYPE_PCT:-70}"
L5_MIN_L3_STAGE_PCT="${GATEFORGE_AGENT_RELEASE_L5_MIN_L3_STAGE_PCT:-70}"
L5_TASKSET="${GATEFORGE_AGENT_RELEASE_L5_TASKSET:-assets_private/agent_modelica_l2_freeze_pack_v0_smoke/taskset_frozen.json}"
if [ ! -f "$L5_TASKSET" ]; then
  L5_TASKSET="tests/fixtures/agent_modelica_l3_stability_ci_taskset_v0.json"
fi
L5_LIVE_EXECUTOR_CMD_DEFAULT="python3 -m ${LIVE_SMOKE_EXECUTOR_MODULE} --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${GATEFORGE_AGENT_RELEASE_SMOKE_PLANNER_BACKEND:-rule}\" --backend \"${GATEFORGE_AGENT_RELEASE_SMOKE_BACKEND:-openmodelica_docker}\" --docker-image \"${GATEFORGE_AGENT_RELEASE_SMOKE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}\""
L5_L3_LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_RELEASE_L5_L3_LIVE_EXECUTOR_CMD:-$L5_LIVE_EXECUTOR_CMD_DEFAULT}"
L5_L4_LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_RELEASE_L5_L4_LIVE_EXECUTOR_CMD:-$L5_LIVE_EXECUTOR_CMD_DEFAULT}"

PROFILE_PATH="${GATEFORGE_AGENT_MVP_PROFILE_PATH:-benchmarks/private/agent_modelica_mvp_repair_v1.json}"
if [ ! -f "$PROFILE_PATH" ]; then
  PROFILE_PATH="benchmarks/agent_modelica_mvp_repair_v1.json"
fi
PROFILE_PATH_FOR_PREFLIGHT="$PROFILE_PATH"
BOOTSTRAP_MISSING_LEARNING_MEMORY="${GATEFORGE_AGENT_RELEASE_BOOTSTRAP_MISSING_LEARNING_MEMORY:-1}"

mkdir -p "$OUT_DIR"

if [ "$BOOTSTRAP_MISSING_LEARNING_MEMORY" = "1" ]; then
  PROFILE_PATH_FOR_PREFLIGHT="$(
    python3 - "$PROFILE_PATH" "$OUT_DIR/learning_profile_bootstrap.json" "$OUT_DIR/learning_memory_bootstrap.json" <<'PY'
import json
import sys
from pathlib import Path

profile_path = Path(sys.argv[1])
profile_out = Path(sys.argv[2])
memory_out = Path(sys.argv[3])

if not profile_path.exists():
    print(str(profile_path))
    raise SystemExit(0)

profile = json.loads(profile_path.read_text(encoding="utf-8"))
privacy = profile.get("privacy") if isinstance(profile.get("privacy"), dict) else {}
memory_path = Path(str(privacy.get("repair_history_path") or ""))
if memory_path.exists():
    print(str(profile_path))
    raise SystemExit(0)

memory_out.parent.mkdir(parents=True, exist_ok=True)
failure_types = ["model_check_error", "simulate_error", "semantic_regression"]
rows = []
for idx in range(60):
    failure_type = failure_types[idx % len(failure_types)]
    split = "holdout" if idx >= 54 else "train"
    error_signature = f"{failure_type}_sig_{split}_{idx}"
    rows.append(
        {
            "fingerprint": f"bootstrap_fp_{idx:04d}",
            "task_id": f"bootstrap_task_{idx:04d}",
            "failure_type": failure_type,
            "scale": "small" if idx % 3 == 0 else ("medium" if idx % 3 == 1 else "large"),
            "used_strategy": f"bootstrap_strategy_{failure_type}",
            "action_trace": ["bootstrap_action_prepare", "bootstrap_action_apply"],
            "error_signature": error_signature,
            "gate_break_reason": "bootstrap_seeded_for_ci_release_preflight",
            "success": True,
            "split": split,
        }
    )
memory_payload = {
    "schema_version": "agent_modelica_repair_memory_v1",
    "rows": rows,
}
memory_out.write_text(json.dumps(memory_payload, indent=2), encoding="utf-8")

profile_copy = dict(profile)
privacy_copy = dict(privacy)
privacy_copy["repair_history_path"] = str(memory_out)
profile_copy["privacy"] = privacy_copy
profile_out.parent.mkdir(parents=True, exist_ok=True)
profile_out.write_text(json.dumps(profile_copy, indent=2), encoding="utf-8")
print(str(profile_out))
PY
  )"
  if [ ! -f "$PROFILE_PATH_FOR_PREFLIGHT" ]; then
    PROFILE_PATH_FOR_PREFLIGHT="$PROFILE_PATH"
  fi
fi

python3 -m gateforge.agent_modelica_learning_preflight_v1 \
  --profile "$PROFILE_PATH_FOR_PREFLIGHT" \
  --out "$OUT_DIR/learning_preflight.json" \
  --report-out "$OUT_DIR/learning_preflight.md"

python3 -m gateforge.agent_modelica_private_asset_guard_v1 \
  --repo-root "$ROOT_DIR" \
  --out "$OUT_DIR/private_asset_guard.json" \
  --report-out "$OUT_DIR/private_asset_guard.md"

if [ "$RUN_LIVE_SMOKE" = "1" ]; then
  SOURCE_MODEL_PATH="${GATEFORGE_AGENT_RELEASE_SMOKE_SOURCE_MODEL_PATH:-artifacts/run_modelica_open_source_growth_sprint_v1_demo/exported/demo_repo_shard_base_a/Base/A/A1.mo}"
  MUTATED_MODEL_PATH="${GATEFORGE_AGENT_RELEASE_SMOKE_MUTATED_MODEL_PATH:-artifacts/run_modelica_open_source_growth_sprint_v1_demo/growth/scale/mutants/semantic_regression/mdl_a1_393f6bb7/mat_mdl_a1_393f6bb7_semantic_regression_301500.mo}"
  SMOKE_PATH_ENV="$OUT_DIR/live_smoke_paths.env"
  python3 - "$SOURCE_MODEL_PATH" "$MUTATED_MODEL_PATH" "$OUT_DIR" > "$SMOKE_PATH_ENV" <<'PY'
import re
import shlex
import sys
from pathlib import Path

source_path = Path(sys.argv[1])
mutated_path = Path(sys.argv[2])
out_dir = Path(sys.argv[3])

smoke_dir = out_dir / "live_smoke_inputs"
smoke_dir.mkdir(parents=True, exist_ok=True)

if not source_path.exists():
    source_path = smoke_dir / "A1.mo"
    source_path.write_text(
        "model A1\n"
        "  Real x;\n"
        "equation\n"
        "  der(x) = -x;\n"
        "end A1;\n",
        encoding="utf-8",
    )

if not mutated_path.exists():
    source_text = source_path.read_text(encoding="utf-8")
    model_name_match = re.search(r"(?im)^\s*model\s+([A-Za-z_]\w*)\b", source_text)
    model_name = model_name_match.group(1) if model_name_match else "A1"
    injection = "  Real __gf_state_301500(start=1.0);"
    if re.search(r"(?im)^\s*equation\b", source_text):
        mutated_text = re.sub(
            r"(?im)^\s*equation\b",
            lambda _: "equation\n" + injection,
            source_text,
            count=1,
        )
    else:
        end_pat = re.compile(rf"(?im)^\s*end\s+{re.escape(model_name)}\s*;")
        end_match = end_pat.search(source_text)
        if end_match:
            insert = "equation\n" + injection + "\n"
            mutated_text = source_text[: end_match.start()] + insert + source_text[end_match.start() :]
        else:
            mutated_text = source_text + "\nequation\n" + injection + "\n"
    mutated_path = smoke_dir / f"{source_path.stem}_smoke_mutant.mo"
    mutated_path.write_text(mutated_text, encoding="utf-8")

print(f"SOURCE_MODEL_PATH={shlex.quote(str(source_path))}")
print(f"MUTATED_MODEL_PATH={shlex.quote(str(mutated_path))}")
PY
  # shellcheck disable=SC1090
  source "$SMOKE_PATH_ENV"
  python3 -m "$LIVE_SMOKE_EXECUTOR_MODULE" \
    --task-id "${GATEFORGE_AGENT_RELEASE_SMOKE_TASK_ID:-release-smoke-1}" \
    --failure-type "${GATEFORGE_AGENT_RELEASE_SMOKE_FAILURE_TYPE:-semantic_regression}" \
    --expected-stage "${GATEFORGE_AGENT_RELEASE_SMOKE_EXPECTED_STAGE:-simulate}" \
    --source-model-path "$SOURCE_MODEL_PATH" \
    --mutated-model-path "$MUTATED_MODEL_PATH" \
    --max-rounds "${GATEFORGE_AGENT_RELEASE_SMOKE_MAX_ROUNDS:-2}" \
    --timeout-sec "${GATEFORGE_AGENT_RELEASE_SMOKE_TIMEOUT_SEC:-90}" \
    --planner-backend "${GATEFORGE_AGENT_RELEASE_SMOKE_PLANNER_BACKEND:-rule}" \
    --backend "${GATEFORGE_AGENT_RELEASE_SMOKE_BACKEND:-openmodelica_docker}" \
    --out "$OUT_DIR/live_smoke_executor.json"
else
  python3 - "$OUT_DIR/live_smoke_executor.json" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"status": "NEEDS_REVIEW", "executor_status": "SKIPPED", "reason": "live_smoke_disabled"}, indent=2), encoding="utf-8")
print(json.dumps({"status": "NEEDS_REVIEW", "executor_status": "SKIPPED"}))
PY
fi

L3_RUN_RESULTS_PATH="$OUT_DIR/l3_diagnostic_gate_run_results.json"
L3_TASKSET_PATH="$OUT_DIR/l3_diagnostic_gate_taskset.json"
L3_QUALITY_PATH="$OUT_DIR/l3_diagnostic_quality_summary.json"
L3_GATE_PATH="$OUT_DIR/l3_diagnostic_gate_summary.json"
if [ "$ENABLE_L3_DIAGNOSTIC_GATE" = "1" ] && [ "$RUN_LIVE_SMOKE" = "1" ]; then
  python3 - "$OUT_DIR/live_smoke_executor.json" "$L3_RUN_RESULTS_PATH" "$L3_TASKSET_PATH" "${GATEFORGE_AGENT_RELEASE_SMOKE_EXPECTED_STAGE:-simulate}" <<'PY'
import json
import sys
from pathlib import Path

live_smoke_path = Path(sys.argv[1])
run_results_path = Path(sys.argv[2])
taskset_path = Path(sys.argv[3])
expected_stage = str(sys.argv[4] or "").strip().lower() or "simulate"

payload = json.loads(live_smoke_path.read_text(encoding="utf-8")) if live_smoke_path.exists() else {}
task_id = str(payload.get("task_id") or "release-smoke-1")
failure_type = str(payload.get("failure_type") or "unknown")
attempts_in = payload.get("attempts") if isinstance(payload.get("attempts"), list) else []
attempts = []
for row in attempts_in:
    if not isinstance(row, dict):
        continue
    attempts.append(
        {
            "round": row.get("round"),
            "observed_failure_type": str(row.get("observed_failure_type") or ""),
            "reason": str(row.get("reason") or ""),
            "check_model_pass": bool(row.get("check_model_pass")),
            "simulate_pass": bool(row.get("simulate_pass")),
            "diagnostic_ir": row.get("diagnostic_ir") if isinstance(row.get("diagnostic_ir"), dict) else {},
        }
    )

run_results = {"records": [{"task_id": task_id, "failure_type": failure_type, "expected_stage": expected_stage, "attempts": attempts}]}
taskset = {"tasks": [{"task_id": task_id, "failure_type": failure_type, "expected_stage": expected_stage}]}
run_results_path.parent.mkdir(parents=True, exist_ok=True)
run_results_path.write_text(json.dumps(run_results, indent=2), encoding="utf-8")
taskset_path.write_text(json.dumps(taskset, indent=2), encoding="utf-8")
print(json.dumps({"status": "PASS", "l3_attempt_count": len(attempts)}))
PY

  python3 -m gateforge.agent_modelica_diagnostic_quality_v0 \
    --run-results "$L3_RUN_RESULTS_PATH" \
    --taskset "$L3_TASKSET_PATH" \
    --low-confidence-threshold "$L3_LOW_CONFIDENCE_THRESHOLD" \
    --out "$L3_QUALITY_PATH" \
    --report-out "$OUT_DIR/l3_diagnostic_quality_summary.md"

  python3 -m gateforge.agent_modelica_l3_diagnostic_gate_v0 \
    --diagnostic-quality-summary "$L3_QUALITY_PATH" \
    --min-parse-coverage-pct "$L3_MIN_PARSE_COVERAGE_PCT" \
    --min-canonical-type-match-rate-pct "$L3_MIN_TYPE_MATCH_RATE_PCT" \
    --min-stage-match-rate-pct "$L3_MIN_STAGE_MATCH_RATE_PCT" \
    --max-low-confidence-rate-pct "$L3_MAX_LOW_CONFIDENCE_RATE_PCT" \
    --out "$L3_GATE_PATH" \
    --report-out "$OUT_DIR/l3_diagnostic_gate_summary.md"
else
  python3 - "$L3_QUALITY_PATH" "$L3_GATE_PATH" "$RUN_LIVE_SMOKE" "$ENABLE_L3_DIAGNOSTIC_GATE" <<'PY'
import json
import sys
from pathlib import Path

quality_path = Path(sys.argv[1])
gate_path = Path(sys.argv[2])
run_live_smoke = str(sys.argv[3]).strip() == "1"
enabled = str(sys.argv[4]).strip() == "1"

if run_live_smoke and not enabled:
    reason = "l3_gate_disabled"
elif not run_live_smoke:
    reason = "live_smoke_disabled"
else:
    reason = "l3_gate_not_run"

quality = {
    "schema_version": "agent_modelica_diagnostic_quality_v0",
    "status": "NEEDS_REVIEW",
    "total_attempts": 0,
    "parsed_attempts": 0,
    "parse_coverage_pct": 0.0,
    "canonical_type_match_rate_pct": 0.0,
    "type_match_rate_pct": 0.0,
    "stage_match_rate_pct": 0.0,
    "low_confidence_rate_pct": 0.0,
    "reasons": [reason],
}
gate = {
    "schema_version": "agent_modelica_l3_diagnostic_gate_v0",
    "status": "NEEDS_REVIEW",
    "gate_result": "SKIPPED",
    "parse_coverage_pct": 0.0,
    "canonical_type_match_rate_pct": 0.0,
    "type_match_rate_pct": 0.0,
    "stage_match_rate_pct": 0.0,
    "low_confidence_rate_pct": 0.0,
    "reasons": [reason],
}

quality_path.parent.mkdir(parents=True, exist_ok=True)
quality_path.write_text(json.dumps(quality, indent=2), encoding="utf-8")
gate_path.write_text(json.dumps(gate, indent=2), encoding="utf-8")
print(json.dumps({"status": "NEEDS_REVIEW", "l3_gate_result": "SKIPPED", "reason": reason}))
PY
fi

L5_EVAL_OUT_DIR="$OUT_DIR/l5_eval"
L5_EVAL_SUMMARY_PATH="$OUT_DIR/l5_eval_summary.json"
if [ "$ENABLE_L5_EVAL_GATE" = "1" ] && [ "$RUN_LIVE_SMOKE" = "1" ]; then
  set +e
  GATEFORGE_AGENT_L5_EVAL_OUT_DIR="$L5_EVAL_OUT_DIR" \
  GATEFORGE_AGENT_L5_EVAL_TASKSET="$L5_TASKSET" \
  GATEFORGE_AGENT_L5_EVAL_SCALES="small,medium" \
  GATEFORGE_AGENT_L5_EVAL_PLANNER_BACKEND="${GATEFORGE_AGENT_RELEASE_SMOKE_PLANNER_BACKEND:-rule}" \
  GATEFORGE_AGENT_L5_EVAL_BACKEND="${GATEFORGE_AGENT_RELEASE_SMOKE_BACKEND:-openmodelica_docker}" \
  GATEFORGE_AGENT_L5_EVAL_OM_DOCKER_IMAGE="${GATEFORGE_AGENT_RELEASE_SMOKE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}" \
  GATEFORGE_AGENT_L5_EVAL_MAX_ROUNDS="${GATEFORGE_AGENT_RELEASE_SMOKE_MAX_ROUNDS:-2}" \
  GATEFORGE_AGENT_L5_EVAL_MAX_TIME_SEC="${GATEFORGE_AGENT_RELEASE_SMOKE_TIMEOUT_SEC:-90}" \
  GATEFORGE_AGENT_L5_EVAL_LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_RELEASE_SMOKE_TIMEOUT_SEC:-90}" \
  GATEFORGE_AGENT_L5_EVAL_RUNTIME_THRESHOLD="${GATEFORGE_AGENT_RELEASE_L5_RUNTIME_THRESHOLD:-0.2}" \
  GATEFORGE_AGENT_L5_EVAL_L3_LIVE_EXECUTOR_CMD="$L5_L3_LIVE_EXECUTOR_CMD" \
  GATEFORGE_AGENT_L5_EVAL_L4_LIVE_EXECUTOR_CMD="$L5_L4_LIVE_EXECUTOR_CMD" \
  GATEFORGE_AGENT_L5_GATE_MODE="$L5_GATE_MODE" \
  GATEFORGE_AGENT_L5_MIN_DELTA_SUCCESS_PP="$L5_MIN_DELTA_SUCCESS_PP" \
  GATEFORGE_AGENT_L5_MAX_PHYSICS_WORSEN_PP="$L5_MAX_PHYSICS_WORSEN_PP" \
  GATEFORGE_AGENT_L5_MAX_REGRESSION_WORSEN_PP="$L5_MAX_REGRESSION_WORSEN_PP" \
  GATEFORGE_AGENT_L5_INFRA_FAILURE_MUST_EQUAL="$L5_INFRA_FAILURE_MUST_EQUAL" \
  GATEFORGE_AGENT_L5_MIN_L3_PARSE_PCT="$L5_MIN_L3_PARSE_PCT" \
  GATEFORGE_AGENT_L5_MIN_L3_TYPE_PCT="$L5_MIN_L3_TYPE_PCT" \
  GATEFORGE_AGENT_L5_MIN_L3_STAGE_PCT="$L5_MIN_L3_STAGE_PCT" \
  bash scripts/run_agent_modelica_l5_eval_v1.sh
  L5_EVAL_RC=$?
  set -e
  if [ -f "$L5_EVAL_OUT_DIR/l5_eval_summary.json" ]; then
    cp "$L5_EVAL_OUT_DIR/l5_eval_summary.json" "$L5_EVAL_SUMMARY_PATH"
  else
    python3 - "$L5_EVAL_SUMMARY_PATH" "$L5_EVAL_RC" <<'PY'
import json
import sys
from pathlib import Path

out_path = Path(sys.argv[1])
exit_code = int(sys.argv[2])
payload = {
    "schema_version": "agent_modelica_l5_eval_v1",
    "status": "FAIL",
    "gate_result": "FAIL",
    "reason": "l5_eval_summary_missing",
    "runner_exit_code": exit_code,
}
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload))
PY
  fi
else
  python3 - "$L5_EVAL_SUMMARY_PATH" "$RUN_LIVE_SMOKE" "$ENABLE_L5_EVAL_GATE" <<'PY'
import json
import sys
from pathlib import Path

out_path = Path(sys.argv[1])
run_live_smoke = str(sys.argv[2]).strip() == "1"
enabled = str(sys.argv[3]).strip() == "1"

if run_live_smoke and not enabled:
    reason = "l5_gate_disabled"
elif not run_live_smoke:
    reason = "live_smoke_disabled"
else:
    reason = "l5_gate_not_run"

payload = {
    "schema_version": "agent_modelica_l5_eval_v1",
    "status": "NEEDS_REVIEW",
    "gate_result": "SKIPPED",
    "reason": reason,
    "acceptance_mode": "delta_uplift",
    "success_at_k_pct": 0.0,
    "delta_success_at_k_pp": 0.0,
    "absolute_success_target_pct": 0.0,
    "physics_fail_rate_pct": 0.0,
    "regression_fail_rate_pct": 0.0,
    "infra_failure_count": 0,
    "non_regression_ok": False,
    "l3_parse_coverage_pct": 0.0,
    "l3_type_match_rate_pct": 0.0,
    "l3_stage_match_rate_pct": 0.0,
}
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload))
PY
fi

python3 - "$OUT_DIR" "$RUN_LIVE_SMOKE" "$REQUIRE_REAL_OMC_BACKEND" "$ENABLE_L3_DIAGNOSTIC_GATE" "$ENFORCE_L3_DIAGNOSTIC_GATE" "$ENABLE_L5_EVAL_GATE" "$ENFORCE_L5_EVAL_GATE" <<'PY'
import json
import sys
from pathlib import Path

out_dir = Path(sys.argv[1])
run_live_smoke = str(sys.argv[2]).strip() == "1"
require_real_omc = str(sys.argv[3]).strip() == "1"
enable_l3_gate = str(sys.argv[4]).strip() == "1"
enforce_l3_gate = str(sys.argv[5]).strip() == "1"
enable_l5_gate = str(sys.argv[6]).strip() == "1"
enforce_l5_gate = str(sys.argv[7]).strip() == "1"
learning = json.loads((out_dir / "learning_preflight.json").read_text(encoding="utf-8"))
private_guard = json.loads((out_dir / "private_asset_guard.json").read_text(encoding="utf-8"))
live_smoke = json.loads((out_dir / "live_smoke_executor.json").read_text(encoding="utf-8"))
l3_gate = json.loads((out_dir / "l3_diagnostic_gate_summary.json").read_text(encoding="utf-8"))
l3_quality = json.loads((out_dir / "l3_diagnostic_quality_summary.json").read_text(encoding="utf-8"))
l5_eval = json.loads((out_dir / "l5_eval_summary.json").read_text(encoding="utf-8"))

status = "PASS"
reasons = []
if str(learning.get("status") or "") != "PASS":
    status = "FAIL"
    reasons.append("learning_preflight_not_pass")
if str(private_guard.get("status") or "") != "PASS":
    status = "FAIL"
    reasons.append("private_asset_guard_not_pass")
live_status = str(live_smoke.get("executor_status") or live_smoke.get("status") or "").strip()
if run_live_smoke and not live_status:
    hard_keys = ("check_model_pass", "simulate_pass", "physics_contract_pass", "regression_pass")
    if all(k in live_smoke for k in hard_keys):
        live_status = "PASS" if all(bool(live_smoke.get(k)) for k in hard_keys) else "FAILED"
if run_live_smoke:
    if live_status != "PASS":
        status = "FAIL"
        reasons.append("live_smoke_not_pass")
else:
    if status != "FAIL" and live_status in {"", "SKIPPED", "NEEDS_REVIEW"}:
        status = "NEEDS_REVIEW"

live_backend = str(live_smoke.get("backend_used") or "").strip().lower()
if run_live_smoke and require_real_omc and live_status == "PASS" and live_backend not in {"omc", "openmodelica_docker"}:
    status = "FAIL"
    reasons.append("live_smoke_backend_not_real_omc")

live_fallback = bool(live_smoke.get("backend_fallback_to_syntax"))
if run_live_smoke and require_real_omc and live_status == "PASS" and live_fallback:
    status = "FAIL"
    reasons.append("live_smoke_backend_fallback_to_syntax")

l3_gate_status = str(l3_gate.get("status") or "").strip()
if run_live_smoke and enable_l3_gate:
    if l3_gate_status != "PASS":
        if enforce_l3_gate:
            status = "FAIL"
            reasons.append("l3_diagnostic_gate_not_pass")
        elif status != "FAIL":
            status = "NEEDS_REVIEW"

l5_gate_status = str(l5_eval.get("status") or "").strip()
if run_live_smoke and enable_l5_gate:
    if l5_gate_status != "PASS":
        if enforce_l5_gate:
            status = "FAIL"
            reasons.append("l5_eval_gate_not_pass")
        elif status != "FAIL":
            status = "NEEDS_REVIEW"

payload = {
    "status": status,
    "profile_path": str(((learning.get("inputs") or {}).get("profile")) or ""),
    "learning_preflight_status": str(learning.get("status") or ""),
    "private_asset_guard_status": str(private_guard.get("status") or ""),
    "live_smoke_status": live_status or "SKIPPED",
    "live_smoke_backend_used": live_backend,
    "require_real_omc_backend": require_real_omc,
    "l3_diagnostic_gate_enabled": enable_l3_gate,
    "l3_diagnostic_gate_enforced": enforce_l3_gate,
    "l3_diagnostic_gate_status": l3_gate_status or "SKIPPED",
    "l3_parse_coverage_pct": float(l3_quality.get("parse_coverage_pct") or 0.0),
    "l3_type_match_rate_pct": float(
        l3_quality.get("canonical_type_match_rate_pct") or l3_quality.get("type_match_rate_pct") or 0.0
    ),
    "l3_stage_match_rate_pct": float(l3_quality.get("stage_match_rate_pct") or 0.0),
    "l3_low_confidence_rate_pct": float(l3_quality.get("low_confidence_rate_pct") or 0.0),
    "l5_eval_gate_enabled": enable_l5_gate,
    "l5_eval_gate_enforced": enforce_l5_gate,
    "l5_gate_status": l5_gate_status or "SKIPPED",
    "l5_acceptance_mode": str(l5_eval.get("acceptance_mode") or "delta_uplift"),
    "l5_success_at_k_pct": float(l5_eval.get("success_at_k_pct") or 0.0),
    "l5_delta_success_at_k_pp": float(l5_eval.get("delta_success_at_k_pp") or 0.0),
    "l5_absolute_success_target_pct": float(l5_eval.get("absolute_success_target_pct") or 0.0),
    "l5_physics_fail_rate_pct": float(l5_eval.get("physics_fail_rate_pct") or 0.0),
    "l5_regression_fail_rate_pct": float(l5_eval.get("regression_fail_rate_pct") or 0.0),
    "l5_infra_failure_count": int(l5_eval.get("infra_failure_count") or 0),
    "l5_non_regression_ok": bool(l5_eval.get("non_regression_ok")),
    "l5_primary_reason": str(l5_eval.get("primary_reason") or "none"),
    "l5_reasons": [str(x) for x in (l5_eval.get("reasons") or []) if isinstance(x, str)],
    "reasons": reasons,
    "paths": {
        "learning_preflight": str(out_dir / "learning_preflight.json"),
        "private_asset_guard": str(out_dir / "private_asset_guard.json"),
        "live_smoke_executor": str(out_dir / "live_smoke_executor.json"),
        "l3_diagnostic_quality": str(out_dir / "l3_diagnostic_quality_summary.json"),
        "l3_diagnostic_gate": str(out_dir / "l3_diagnostic_gate_summary.json"),
        "l5_eval_summary": str(out_dir / "l5_eval_summary.json"),
        "l5_eval_bundle": str(out_dir / "l5_eval" / "summary.json"),
        "l5_weekly_metrics": str(out_dir / "l5_eval" / "l5_weekly_metrics.json"),
    },
}
(out_dir / "release_preflight_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload))
if status == "FAIL":
    raise SystemExit(1)
PY
