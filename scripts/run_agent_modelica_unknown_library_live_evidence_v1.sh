#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_LIVE_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_unknown_library_live_evidence_v1}"
RUN_ID="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_RUN_ID:-$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).strftime("unknownlib_live_%Y%m%dT%H%M%SZ"))
PY
)}"
RUN_ROOT_DEFAULT="$OUT_DIR/runs/$RUN_ID"
RUN_ROOT="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_RUN_ROOT:-$RUN_ROOT_DEFAULT}"
RESUME="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_RESUME:-0}"
RESUME_STAGES="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_RESUME_STAGES:-auto}"
FORCE_RERUN_COMPLETED="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_FORCE_RERUN_COMPLETED:-0}"
UPDATE_LATEST="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_UPDATE_LATEST:-1}"
STOP_AFTER_STAGE="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_STOP_AFTER_STAGE:-}"

MANIFEST_PATH="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_MANIFEST:-assets_private/agent_modelica_unknown_library_pool_v1/manifest.json}"
EXCLUDE_MODELS_JSON="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_EXCLUDE_MODELS_JSON:-}"
REPAIR_MEMORY_PATH="${GATEFORGE_AGENT_REPAIR_MEMORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"
PATCH_TEMPLATE_ADAPTATIONS_PATH="${GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH:-data/private_failure_corpus/agent_modelica_patch_template_adaptations_v1.json}"
RETRIEVAL_POLICY_PATH="${GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH:-data/private_failure_corpus/agent_modelica_retrieval_policy_v1.json}"

FAILURE_TYPES="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_FAILURE_TYPES:-underconstrained_system,connector_mismatch,initialization_infeasible}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_SPLIT_SEED:-agent_modelica_unknown_library_taskset_v1}"

MAX_ROUNDS="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_MAX_ROUNDS:-2}"
MAX_TIME_SEC="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_MAX_TIME_SEC:-180}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_LIVE_TIMEOUT_SEC:-180}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_LIVE_MAX_OUTPUT_CHARS:-2400}"

PLANNER_BACKEND="${GATEFORGE_AGENT_LIVE_PLANNER_BACKEND:-gemini}"
OM_BACKEND="${GATEFORGE_AGENT_LIVE_OM_BACKEND:-openmodelica_docker}"
OM_DOCKER_IMAGE="${GATEFORGE_AGENT_LIVE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"
RUN_BACKEND_PREFLIGHT="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_RUN_BACKEND_PREFLIGHT:-1}"
MIN_RETRIEVAL_COVERAGE_PCT="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_MIN_RETRIEVAL_COVERAGE_PCT:-50.0}"
MIN_DIAGNOSTIC_PARSE_COVERAGE_PCT="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_MIN_DIAGNOSTIC_PARSE_COVERAGE_PCT:-95.0}"
MIN_RETRIEVAL_ON_SUCCESS_AT_K_PCT="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_MIN_RETRIEVAL_ON_SUCCESS_AT_K_PCT:-1.0}"
STORE_MEMORY_AFTER_RUN="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_STORE_MEMORY_AFTER_RUN:-0}"
TASKSET_MODULE="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_TASKSET_MODULE:-gateforge.agent_modelica_unknown_library_taskset_v1}"
CURATED_RETRIEVAL_MODULE="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_CURATED_RETRIEVAL_MODULE:-gateforge.agent_modelica_unknown_library_curated_retrieval_v1}"
RETRIEVAL_SUMMARY_MODULE="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_RETRIEVAL_SUMMARY_MODULE:-gateforge.agent_modelica_unknown_library_retrieval_summary_v1}"
EVIDENCE_MODULE="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_EVIDENCE_MODULE:-gateforge.agent_modelica_unknown_library_evidence_v1}"

DEFAULT_LIVE_EXECUTOR_CMD="python3 -m gateforge.agent_modelica_live_executor_gemini_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --source-library-path \"__SOURCE_LIBRARY_PATH__\" --source-package-name \"__SOURCE_PACKAGE_NAME__\" --source-library-model-path \"__SOURCE_LIBRARY_MODEL_PATH__\" --source-qualified-model-name \"__SOURCE_QUALIFIED_MODEL_NAME__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${PLANNER_BACKEND}\" --backend \"${OM_BACKEND}\" --docker-image \"${OM_DOCKER_IMAGE}\""
LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_LIVE_EXECUTOR_CMD:-$DEFAULT_LIVE_EXECUTOR_CMD}"

ALL_STAGES=(
  "backend_preflight"
  "challenge"
  "curated_retrieval"
  "baseline_off_live"
  "retrieval_on_live"
  "diagnostic_quality"
  "retrieval_summary"
  "evidence"
  "repair_memory_store"
)

resolve_resume_target() {
  if [ "$RESUME" != "1" ]; then
    return 0
  fi
  eval "$(
    python3 - "$OUT_DIR" "$RUN_ID" "$RUN_ROOT" <<'PY'
import json
import sys
from pathlib import Path

out_dir = Path(sys.argv[1])
run_id = str(sys.argv[2] or "").strip()
run_root = str(sys.argv[3] or "").strip()

if run_root:
    root = Path(run_root)
elif run_id:
    root = out_dir / "runs" / run_id
else:
    latest = {}
    latest_path = out_dir / "latest_run.json"
    if latest_path.exists():
        try:
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
        except Exception:
            latest = {}
    root = Path(str(latest.get("run_root") or out_dir / "runs" / ""))
    run_id = str(latest.get("run_id") or "")

if not run_id and root.name:
    run_id = root.name

print(f"RUN_ID={json.dumps(run_id)}")
print(f"RUN_ROOT={json.dumps(str(root))}")
PY
  )"
}

resolve_resume_target

CHALLENGE_DIR="$RUN_ROOT/challenge"
CURATED_DIR="$RUN_ROOT/curated_retrieval"
BASELINE_DIR="$RUN_ROOT/baseline_off_live"
RETRIEVAL_DIR="$RUN_ROOT/retrieval_on_live"
OM_LIBRARY_CACHE="${GATEFORGE_AGENT_OM_LIBRARY_CACHE:-$RUN_ROOT/.omlibrary_cache}"
BACKEND_PREFLIGHT_PATH="$RUN_ROOT/backend_preflight.json"
MERGED_HISTORY_PATH="$RUN_ROOT/merged_repair_history.json"
RETRIEVAL_SUMMARY_PATH="$RUN_ROOT/retrieval_summary.json"
EVIDENCE_SUMMARY_PATH="$RUN_ROOT/evidence_summary.json"
GATE_SUMMARY_PATH="$RUN_ROOT/gate_summary.json"
DECISION_SUMMARY_PATH="$RUN_ROOT/decision_summary.json"
SOURCE_UNSTABLE_EXCLUSIONS_PATH="$RUN_ROOT/source_unstable_exclusions.json"
FINAL_RUN_SUMMARY_PATH="$RUN_ROOT/final_run_summary.json"
RUN_MANIFEST_PATH="$RUN_ROOT/run_manifest.json"

mkdir -p "$OUT_DIR" "$OUT_DIR/runs" "$RUN_ROOT" "$CHALLENGE_DIR" "$CURATED_DIR" "$BASELINE_DIR" "$RETRIEVAL_DIR" "$OM_LIBRARY_CACHE"
OM_LIBRARY_CACHE="$(cd "$OM_LIBRARY_CACHE" && pwd)"
export GATEFORGE_OM_DOCKER_LIBRARY_CACHE="$OM_LIBRARY_CACHE"

if [ ! -f "$MANIFEST_PATH" ]; then
  echo "Missing unknown-library manifest: $MANIFEST_PATH" >&2
  exit 1
fi

init_run_manifest() {
  python3 - "$RUN_MANIFEST_PATH" "$OUT_DIR" "$RUN_ROOT" "$RUN_ID" "$MANIFEST_PATH" "$UPDATE_LATEST" "$RESUME" "$RESUME_STAGES" "$FORCE_RERUN_COMPLETED" "$STOP_AFTER_STAGE" "$FAILURE_TYPES" "$HOLDOUT_RATIO" "$SPLIT_SEED" "$MAX_ROUNDS" "$MAX_TIME_SEC" "$RUNTIME_THRESHOLD" "$LIVE_TIMEOUT_SEC" "$LIVE_MAX_OUTPUT_CHARS" "$PLANNER_BACKEND" "$OM_BACKEND" "$OM_DOCKER_IMAGE" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    manifest_path,
    out_dir,
    run_root,
    run_id,
    source_manifest,
    update_latest,
    resume,
    resume_stages,
    force_rerun_completed,
    stop_after_stage,
    failure_types,
    holdout_ratio,
    split_seed,
    max_rounds,
    max_time_sec,
    runtime_threshold,
    live_timeout_sec,
    live_max_output_chars,
    planner_backend,
    om_backend,
    om_docker_image,
) = sys.argv[1:]

payload = {
    "schema_version": "agent_modelica_unknown_library_live_run_manifest_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_id": run_id,
    "out_dir": out_dir,
    "run_root": run_root,
    "source_manifest": source_manifest,
    "update_latest": str(update_latest) == "1",
    "runtime_config": {
        "resume": str(resume) == "1",
        "resume_stages": resume_stages,
        "force_rerun_completed": str(force_rerun_completed) == "1",
        "stop_after_stage": stop_after_stage,
        "failure_types": failure_types,
        "holdout_ratio": float(holdout_ratio),
        "split_seed": split_seed,
        "max_rounds": int(max_rounds),
        "max_time_sec": int(max_time_sec),
        "runtime_threshold": float(runtime_threshold),
        "live_timeout_sec": int(live_timeout_sec),
        "live_max_output_chars": int(live_max_output_chars),
        "planner_backend": planner_backend,
        "om_backend": om_backend,
        "om_docker_image": om_docker_image,
    },
}
path = Path(manifest_path)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY
}

stage_update() {
  local stage="$1"
  local status="$2"
  local exit_code="$3"
  local summary_path="$4"
  local details_json="${5:-{}}"
  python3 - "$RUN_ROOT" "$stage" "$status" "$exit_code" "$summary_path" "$details_json" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

run_root, stage, status, exit_code, summary_path, details_json = sys.argv[1:]
payload = {
    "schema_version": "agent_modelica_unknown_library_live_stage_status_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "stage": stage,
    "status": status,
    "exit_code": int(exit_code),
    "summary_path": summary_path,
    "complete": status in {"PASS", "FAIL", "NEEDS_REVIEW", "SKIPPED"},
    "details": {},
}
try:
    details = json.loads(details_json)
    if isinstance(details, dict):
        payload["details"] = details
except Exception:
    payload["details"] = {}
path = Path(run_root) / "stages" / stage / "stage_status.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY
}

stage_complete() {
  local stage="$1"
  python3 - "$RUN_ROOT" "$stage" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1]) / "stages" / sys.argv[2] / "stage_status.json"
if not path.exists():
    raise SystemExit(1)
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)
status = str(payload.get("status") or "").upper()
complete = bool(payload.get("complete"))
raise SystemExit(0 if complete and status in {"PASS", "NEEDS_REVIEW", "SKIPPED"} else 1)
PY
}

summary_status() {
  local summary_path="$1"
  local rc="$2"
  python3 - "$summary_path" "$rc" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
rc = int(sys.argv[2])
if not path.exists():
    print("PASS" if rc == 0 else "FAIL")
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("PASS" if rc == 0 else "FAIL")
    raise SystemExit(0)
status = str(payload.get("status") or "").strip().upper()
print(status or ("PASS" if rc == 0 else "FAIL"))
PY
}

stage_requested() {
  local stage="$1"
  if [ ",$STAGE_SELECTION_CSV," = ",," ]; then
    return 1
  fi
  case ",$STAGE_SELECTION_CSV," in
    *",$stage,"*) return 0 ;;
    *) return 1 ;;
  esac
}

compute_stage_selection() {
  if [ "$RESUME" != "1" ]; then
    STAGE_SELECTION_CSV="$(IFS=,; echo "${ALL_STAGES[*]}")"
    return 0
  fi
  if [ "$RESUME_STAGES" != "auto" ]; then
    STAGE_SELECTION_CSV="$RESUME_STAGES"
    return 0
  fi
  local found=0
  local stages=()
  local stage
  for stage in "${ALL_STAGES[@]}"; do
    if [ "$found" = "1" ]; then
      stages+=("$stage")
      continue
    fi
    if ! stage_complete "$stage"; then
      found=1
      stages+=("$stage")
    fi
  done
  STAGE_SELECTION_CSV="$(IFS=,; echo "${stages[*]}")"
}

finalize_run() {
  if [ ! -f "$DECISION_SUMMARY_PATH" ]; then
    return 0
  fi
  python3 - "$FINAL_RUN_SUMMARY_PATH" "$DECISION_SUMMARY_PATH" "$EVIDENCE_SUMMARY_PATH" "$GATE_SUMMARY_PATH" "$RUN_ID" "$RUN_ROOT" "$OUT_DIR" "$UPDATE_LATEST" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

final_path, decision_path, evidence_path, gate_path, run_id, run_root, out_dir, update_latest = sys.argv[1:]

def _load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}

decision = _load(decision_path)
evidence = _load(evidence_path)
gate = _load(gate_path)
summary = {
    "schema_version": "agent_modelica_unknown_library_live_final_run_summary_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_id": run_id,
    "run_root": run_root,
    "status": str(decision.get("status") or gate.get("status") or evidence.get("status") or ""),
    "decision": str(decision.get("decision") or ""),
    "primary_reason": str(decision.get("primary_reason") or gate.get("primary_reason") or ""),
    "counts_by_library": decision.get("counts_by_library") if isinstance(decision.get("counts_by_library"), dict) else {},
    "retrieval_coverage_pct": decision.get("retrieval_coverage_pct"),
    "non_regression_status": decision.get("non_regression_status"),
    "success_by_library": decision.get("success_by_library") if isinstance(decision.get("success_by_library"), dict) else {},
    "paths": {
        "evidence_summary": evidence_path,
        "gate_summary": gate_path,
        "decision_summary": decision_path,
    },
}
final = Path(final_path)
final.parent.mkdir(parents=True, exist_ok=True)
final.write_text(json.dumps(summary, indent=2), encoding="utf-8")

if str(update_latest) != "1":
    raise SystemExit(0)

out_root = Path(out_dir)
latest_run = {
    "schema_version": "agent_modelica_unknown_library_live_latest_run_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_id": run_id,
    "run_root": run_root,
    "status": summary["status"],
    "decision": summary["decision"],
    "summary_path": str(final),
}
for name, payload in (
    ("latest_run.json", latest_run),
    ("latest_summary.json", summary),
    ("latest_decision_summary.json", decision),
):
    path = out_root / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY
}

maybe_stop_after_stage() {
  local stage="$1"
  if [ -n "$STOP_AFTER_STAGE" ] && [ "$STOP_AFTER_STAGE" = "$stage" ]; then
    echo "Stopped after stage: $stage"
    exit 0
  fi
}

run_backend_preflight_stage() {
  if [ "$RUN_BACKEND_PREFLIGHT" != "1" ]; then
    python3 - "$BACKEND_PREFLIGHT_PATH" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
path = Path(sys.argv[1])
path.write_text(json.dumps({"schema_version": "agent_modelica_unknown_library_backend_preflight_v1", "generated_at_utc": datetime.now(timezone.utc).isoformat(), "status": "SKIPPED", "reason": "backend_preflight_disabled"}, indent=2), encoding="utf-8")
PY
    return 0
  fi
  python3 -m gateforge.smoke --backend "$OM_BACKEND" --out "$BACKEND_PREFLIGHT_PATH"
}

run_challenge_stage() {
  local args=(
    python3 -m "$TASKSET_MODULE"
    --manifest "$MANIFEST_PATH" \
    --out-dir "$CHALLENGE_DIR" \
    --failure-types "$FAILURE_TYPES" \
    --holdout-ratio "$HOLDOUT_RATIO" \
    --seed "$SPLIT_SEED"
  )
  if [ -n "$EXCLUDE_MODELS_JSON" ] && [ -f "$EXCLUDE_MODELS_JSON" ]; then
    args+=(--exclude-models-json "$EXCLUDE_MODELS_JSON")
  fi
  "${args[@]}"
}

run_curated_retrieval_stage() {
  python3 -m "$CURATED_RETRIEVAL_MODULE" \
    --manifest "$MANIFEST_PATH" \
    --failure-types "$FAILURE_TYPES" \
    --history-out "$CURATED_DIR/history.json" \
    --out "$CURATED_DIR/summary.json"

  python3 - "$REPAIR_MEMORY_PATH" "$CURATED_DIR/history.json" "$MERGED_HISTORY_PATH" <<'PY'
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
curated_rows = curated.get("rows") if isinstance(curated.get("rows"), list) else []
rows.extend([row for row in curated_rows if isinstance(row, dict)])

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps({"schema_version": "agent_modelica_unknown_library_merged_history_v1", "rows": rows}, indent=2), encoding="utf-8")
PY
}

run_baseline_off_live_stage() {
  local args=(
    python3 -m gateforge.agent_modelica_run_contract_v1
    --taskset "$CHALLENGE_DIR/taskset_frozen.json"
    --mode live
    --max-rounds "$MAX_ROUNDS"
    --max-time-sec "$MAX_TIME_SEC"
    --runtime-threshold "$RUNTIME_THRESHOLD"
    --patch-template-adaptations "$PATCH_TEMPLATE_ADAPTATIONS_PATH"
    --retrieval-policy "$RETRIEVAL_POLICY_PATH"
    --live-executor-cmd "$LIVE_EXECUTOR_CMD"
    --live-timeout-sec "$LIVE_TIMEOUT_SEC"
    --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS"
    --records-jsonl "$BASELINE_DIR/records.jsonl"
    --results-out "$BASELINE_DIR/results.json"
    --out "$BASELINE_DIR/summary.json"
  )
  if [ "$RESUME" = "1" ] && [ -f "$BASELINE_DIR/records.jsonl" ]; then
    args+=(--resume-from-records)
  fi
  "${args[@]}"
}

run_retrieval_on_live_stage() {
  local args=(
    python3 -m gateforge.agent_modelica_run_contract_v1
    --taskset "$CHALLENGE_DIR/taskset_frozen.json"
    --mode live
    --max-rounds "$MAX_ROUNDS"
    --max-time-sec "$MAX_TIME_SEC"
    --runtime-threshold "$RUNTIME_THRESHOLD"
    --repair-history "$MERGED_HISTORY_PATH"
    --patch-template-adaptations "$PATCH_TEMPLATE_ADAPTATIONS_PATH"
    --retrieval-policy "$RETRIEVAL_POLICY_PATH"
    --live-executor-cmd "$LIVE_EXECUTOR_CMD"
    --live-timeout-sec "$LIVE_TIMEOUT_SEC"
    --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS"
    --records-jsonl "$RETRIEVAL_DIR/records.jsonl"
    --results-out "$RETRIEVAL_DIR/results.json"
    --out "$RETRIEVAL_DIR/summary.json"
  )
  if [ "$RESUME" = "1" ] && [ -f "$RETRIEVAL_DIR/records.jsonl" ]; then
    args+=(--resume-from-records)
  fi
  "${args[@]}"
}

run_diagnostic_quality_stage() {
  python3 -m gateforge.agent_modelica_diagnostic_quality_v0 \
    --run-results "$BASELINE_DIR/results.json" \
    --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
    --out "$BASELINE_DIR/diagnostic_quality_summary.json"

  python3 -m gateforge.agent_modelica_diagnostic_quality_v0 \
    --run-results "$RETRIEVAL_DIR/results.json" \
    --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
    --out "$RETRIEVAL_DIR/diagnostic_quality_summary.json"
}

run_retrieval_summary_stage() {
  python3 -m "$RETRIEVAL_SUMMARY_MODULE" \
    --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
    --results "$RETRIEVAL_DIR/results.json" \
    --out "$RETRIEVAL_SUMMARY_PATH"
}

run_evidence_stage() {
  python3 -m "$EVIDENCE_MODULE" \
    --challenge-summary "$CHALLENGE_DIR/summary.json" \
    --baseline-off-summary "$BASELINE_DIR/summary.json" \
    --baseline-off-results "$BASELINE_DIR/results.json" \
    --retrieval-on-summary "$RETRIEVAL_DIR/summary.json" \
    --retrieval-on-results "$RETRIEVAL_DIR/results.json" \
    --retrieval-summary "$RETRIEVAL_SUMMARY_PATH" \
    --min-retrieval-on-success-at-k-pct "$MIN_RETRIEVAL_ON_SUCCESS_AT_K_PCT" \
    --min-retrieval-coverage-pct "$MIN_RETRIEVAL_COVERAGE_PCT" \
    --min-diagnostic-parse-coverage-pct "$MIN_DIAGNOSTIC_PARSE_COVERAGE_PCT" \
    --out "$EVIDENCE_SUMMARY_PATH" \
    --gate-out "$GATE_SUMMARY_PATH" \
    --decision-out "$DECISION_SUMMARY_PATH" \
    --source-unstable-exclusions-out "$SOURCE_UNSTABLE_EXCLUSIONS_PATH"
}

run_repair_memory_store_stage() {
  if [ "$STORE_MEMORY_AFTER_RUN" != "1" ]; then
    python3 - "$RUN_ROOT/repair_memory_summary.json" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
path = Path(sys.argv[1])
path.write_text(json.dumps({"schema_version": "agent_modelica_unknown_library_repair_memory_stage_v1", "generated_at_utc": datetime.now(timezone.utc).isoformat(), "status": "SKIPPED", "reason": "memory_store_disabled"}, indent=2), encoding="utf-8")
PY
    return 0
  fi
  python3 -m gateforge.agent_modelica_repair_memory_store_v1 \
    --run-results "$RETRIEVAL_DIR/results.json" \
    --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
    --memory "$REPAIR_MEMORY_PATH" \
    --include-failed \
    --out "$RUN_ROOT/repair_memory_summary.json"
}

run_stage() {
  local stage="$1"
  local summary_path="$2"
  local func_name="$3"
  local details_json="${4:-{}}"

  if ! stage_requested "$stage"; then
    return 0
  fi
  if [ "$FORCE_RERUN_COMPLETED" != "1" ] && stage_complete "$stage"; then
    return 0
  fi

  stage_update "$stage" "RUNNING" 0 "$summary_path" "$details_json"
  set +e
  "$func_name"
  local rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    stage_update "$stage" "FAIL" "$rc" "$summary_path" "$details_json"
    exit "$rc"
  fi
  local status
  status="$(summary_status "$summary_path" "$rc")"
  stage_update "$stage" "$status" "$rc" "$summary_path" "$details_json"
  maybe_stop_after_stage "$stage"
}

init_run_manifest
compute_stage_selection

if [ "$RESUME" = "1" ] && [ -z "$STAGE_SELECTION_CSV" ]; then
  finalize_run
  if [ -f "$FINAL_RUN_SUMMARY_PATH" ]; then
    cat "$FINAL_RUN_SUMMARY_PATH"
  fi
  exit 0
fi

run_stage "backend_preflight" "$BACKEND_PREFLIGHT_PATH" "run_backend_preflight_stage"
run_stage "challenge" "$CHALLENGE_DIR/summary.json" "run_challenge_stage"
run_stage "curated_retrieval" "$CURATED_DIR/summary.json" "run_curated_retrieval_stage"
run_stage "baseline_off_live" "$BASELINE_DIR/summary.json" "run_baseline_off_live_stage"
run_stage "retrieval_on_live" "$RETRIEVAL_DIR/summary.json" "run_retrieval_on_live_stage"
run_stage "diagnostic_quality" "$RETRIEVAL_DIR/diagnostic_quality_summary.json" "run_diagnostic_quality_stage"
run_stage "retrieval_summary" "$RETRIEVAL_SUMMARY_PATH" "run_retrieval_summary_stage"
run_stage "evidence" "$DECISION_SUMMARY_PATH" "run_evidence_stage"
run_stage "repair_memory_store" "$RUN_ROOT/repair_memory_summary.json" "run_repair_memory_store_stage"

finalize_run
cat "$FINAL_RUN_SUMMARY_PATH"
