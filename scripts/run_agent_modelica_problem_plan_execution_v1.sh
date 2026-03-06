#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PLAN_PATH="${GATEFORGE_AGENT_PROBLEM_PLAN_PATH:-artifacts/agent_modelica_mutation_plan_builder_v1_demo/plan.json}"
OUT_ROOT="${GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_OUT_DIR:-artifacts/agent_modelica_problem_plan_execution_v1}"
RUNNER_SCRIPT="${GATEFORGE_AGENT_MUTATION_BATCH_RUNNER:-scripts/run_private_model_mutation_scale_batch_v1.sh}"
EXECUTION_PROFILE="${GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_PROFILE:-quick}"
STRICT_OMC="${GATEFORGE_AGENT_PROBLEM_PLAN_STRICT_OMC:-1}"
SKIP_OMC_PREFLIGHT="${GATEFORGE_AGENT_PROBLEM_PLAN_SKIP_OMC_PREFLIGHT:-0}"

mkdir -p "$OUT_ROOT"

if [ ! -f "$PLAN_PATH" ]; then
  echo "{\"status\":\"FAIL\",\"reason\":\"plan_missing\",\"plan_path\":\"$PLAN_PATH\"}" >&2
  exit 1
fi
if [ ! -f "$RUNNER_SCRIPT" ]; then
  echo "{\"status\":\"FAIL\",\"reason\":\"runner_missing\",\"runner_script\":\"$RUNNER_SCRIPT\"}" >&2
  exit 1
fi

if [ "$EXECUTION_PROFILE" = "full" ]; then
  DEFAULT_MUTATIONS_PER_FAILURE_TYPE="2"
  DEFAULT_MIN_GENERATED_MUTATIONS="18"
  DEFAULT_MAX_MUTATION_MODELS="80"
else
  DEFAULT_MUTATIONS_PER_FAILURE_TYPE="1"
  DEFAULT_MIN_GENERATED_MUTATIONS="4"
  DEFAULT_MAX_MUTATION_MODELS="8"
fi

MUTATIONS_PER_FAILURE_TYPE="${GATEFORGE_MUTATIONS_PER_FAILURE_TYPE:-$DEFAULT_MUTATIONS_PER_FAILURE_TYPE}"
MIN_GENERATED_MUTATIONS="${GATEFORGE_MIN_GENERATED_MUTATIONS:-$DEFAULT_MIN_GENERATED_MUTATIONS}"
MAX_MUTATION_MODELS="${GATEFORGE_MAX_MUTATION_MODELS:-$DEFAULT_MAX_MUTATION_MODELS}"
if [ -n "${GATEFORGE_TARGET_SCALES:-}" ]; then
  TARGET_SCALES="${GATEFORGE_TARGET_SCALES}"
elif [ "$STRICT_OMC" = "1" ]; then
  TARGET_SCALES="small,medium,large"
else
  TARGET_SCALES="small,medium,large"
fi
VALIDATION_MAX_MUTATIONS="${GATEFORGE_MUTATION_VALIDATION_MAX_MUTATIONS:-300}"
VALIDATION_MAX_BASELINES="${GATEFORGE_MUTATION_VALIDATION_MAX_BASELINES:-120}"
VALIDATION_BACKEND="${GATEFORGE_MUTATION_VALIDATION_BACKEND:-auto}"
STRICT_MIN_TYPE_MATCH_PCT="${GATEFORGE_AGENT_PROBLEM_PLAN_STRICT_MIN_TYPE_MATCH_PCT:-35}"
STRICT_MIN_STAGE_MATCH_PCT="${GATEFORGE_AGENT_PROBLEM_PLAN_STRICT_MIN_STAGE_MATCH_PCT:-45}"
if [ "$STRICT_OMC" = "1" ]; then
  VALIDATION_BACKEND="omc"
fi

export GATEFORGE_MUTATIONS_PER_FAILURE_TYPE="$MUTATIONS_PER_FAILURE_TYPE"
export GATEFORGE_MIN_GENERATED_MUTATIONS="$MIN_GENERATED_MUTATIONS"
export GATEFORGE_MAX_MUTATION_MODELS="$MAX_MUTATION_MODELS"
export GATEFORGE_TARGET_SCALES="$TARGET_SCALES"
export GATEFORGE_MUTATION_VALIDATION_MAX_MUTATIONS="$VALIDATION_MAX_MUTATIONS"
export GATEFORGE_MUTATION_VALIDATION_MAX_BASELINES="$VALIDATION_MAX_BASELINES"
export GATEFORGE_MUTATION_VALIDATION_BACKEND="$VALIDATION_BACKEND"
if [ "$STRICT_OMC" = "1" ]; then
  export GATEFORGE_MUTATION_VALIDATION_MIN_TYPE_MATCH_PCT="${GATEFORGE_MUTATION_VALIDATION_MIN_TYPE_MATCH_PCT:-$STRICT_MIN_TYPE_MATCH_PCT}"
  export GATEFORGE_MUTATION_VALIDATION_MIN_STAGE_MATCH_PCT="${GATEFORGE_MUTATION_VALIDATION_MIN_STAGE_MATCH_PCT:-$STRICT_MIN_STAGE_MATCH_PCT}"
fi
export GATEFORGE_MIN_ACCEPTED_MODELS="${GATEFORGE_MIN_ACCEPTED_MODELS:-1}"
export GATEFORGE_MIN_ACCEPTED_LARGE_MODELS="${GATEFORGE_MIN_ACCEPTED_LARGE_MODELS:-0}"
export GATEFORGE_MIN_ACCEPTED_LARGE_RATIO_PCT="${GATEFORGE_MIN_ACCEPTED_LARGE_RATIO_PCT:-0}"
export GATEFORGE_MIN_SELECTED_MODELS="${GATEFORGE_MIN_SELECTED_MODELS:-1}"
export GATEFORGE_HARD_MOAT_MIN_DISCOVERED_MODELS="${GATEFORGE_HARD_MOAT_MIN_DISCOVERED_MODELS:-1}"
export GATEFORGE_HARD_MOAT_MIN_ACCEPTED_MODELS="${GATEFORGE_HARD_MOAT_MIN_ACCEPTED_MODELS:-1}"
export GATEFORGE_HARD_MOAT_MIN_ACCEPTED_LARGE_MODELS="${GATEFORGE_HARD_MOAT_MIN_ACCEPTED_LARGE_MODELS:-0}"
export GATEFORGE_HARD_MOAT_MIN_ACCEPTED_LARGE_RATIO_PCT="${GATEFORGE_HARD_MOAT_MIN_ACCEPTED_LARGE_RATIO_PCT:-0}"
export GATEFORGE_HARD_MOAT_MIN_GENERATED_MUTATIONS="${GATEFORGE_HARD_MOAT_MIN_GENERATED_MUTATIONS:-1}"
export GATEFORGE_HARD_MOAT_MIN_REPRODUCIBLE_MUTATIONS="${GATEFORGE_HARD_MOAT_MIN_REPRODUCIBLE_MUTATIONS:-0}"
export GATEFORGE_HARD_MOAT_MIN_CANONICAL_NET_GROWTH_MODELS="${GATEFORGE_HARD_MOAT_MIN_CANONICAL_NET_GROWTH_MODELS:-0}"
export GATEFORGE_HARD_MOAT_MIN_VALIDATION_TYPE_MATCH_RATE_PCT="${GATEFORGE_HARD_MOAT_MIN_VALIDATION_TYPE_MATCH_RATE_PCT:-0}"
export GATEFORGE_HARD_MOAT_MIN_FAILURE_TYPE_ENTROPY="${GATEFORGE_HARD_MOAT_MIN_FAILURE_TYPE_ENTROPY:-0}"
export GATEFORGE_HARD_MOAT_MAX_DISTRIBUTION_DRIFT_TVD="${GATEFORGE_HARD_MOAT_MAX_DISTRIBUTION_DRIFT_TVD:-1.0}"

# Fail fast in strict mode when no executable OMC backend is actually available.
if [ "$SKIP_OMC_PREFLIGHT" != "1" ]; then
python3 - "$STRICT_OMC" "$VALIDATION_BACKEND" <<'PY'
import json
import shutil
import subprocess
import sys

strict = str(sys.argv[1]).strip() == "1"
backend_requested = str(sys.argv[2]).strip().lower() or "auto"

if not strict:
    print(json.dumps({"status": "PASS", "omc_preflight": "skipped_non_strict"}))
    raise SystemExit(0)

has_omc = shutil.which("omc") is not None
has_docker = shutil.which("docker") is not None
docker_ok = False
docker_error = ""

if has_docker:
    try:
        proc = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
        docker_ok = proc.returncode == 0 and bool((proc.stdout or "").strip())
        if not docker_ok:
            docker_error = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()[:240]
    except Exception as exc:  # pragma: no cover - defensive, shell preflight only
        docker_error = str(exc)

if backend_requested == "openmodelica_docker":
    if not docker_ok:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "reason": "strict_omc_preflight_failed",
                    "backend_requested": backend_requested,
                    "has_omc": has_omc,
                    "has_docker": has_docker,
                    "docker_ok": docker_ok,
                    "docker_error_excerpt": docker_error,
                }
            )
        )
        raise SystemExit(1)
    print(json.dumps({"status": "PASS", "omc_preflight_backend": "openmodelica_docker"}))
    raise SystemExit(0)

# For strict mode with backend=omc/auto:
# allow local omc first; otherwise require docker daemon to be reachable.
if has_omc:
    print(json.dumps({"status": "PASS", "omc_preflight_backend": "omc"}))
    raise SystemExit(0)
if docker_ok:
    print(json.dumps({"status": "PASS", "omc_preflight_backend": "openmodelica_docker"}))
    raise SystemExit(0)

print(
    json.dumps(
        {
            "status": "FAIL",
            "reason": "strict_omc_preflight_failed",
            "backend_requested": backend_requested,
            "has_omc": has_omc,
            "has_docker": has_docker,
            "docker_ok": docker_ok,
            "docker_error_excerpt": docker_error,
        }
    )
)
raise SystemExit(1)
PY
fi

# Quick strict mode defaults to a curated low-dependency pool for fast iteration.
FORCE_CURATED_ROOTS="${GATEFORGE_AGENT_PROBLEM_PLAN_FORCE_CURATED_ROOTS:-1}"
CURATED_ROOTS="${GATEFORGE_AGENT_PROBLEM_PLAN_CURATED_MODEL_ROOTS:-artifacts/run_private_model_mutation_scale_batch_v1_demo/private_models:artifacts/run_modelica_open_source_growth_sprint_v1_demo/exported/demo_repo_shard_base_a}"
if [ "$STRICT_OMC" = "1" ] && [ "$EXECUTION_PROFILE" != "full" ] && [ "$FORCE_CURATED_ROOTS" = "1" ]; then
  export GATEFORGE_PRIVATE_MODEL_ROOTS="$CURATED_ROOTS"
elif [ -z "${GATEFORGE_PRIVATE_MODEL_ROOTS:-}" ] && [ "$STRICT_OMC" = "1" ] && [ "$EXECUTION_PROFILE" != "full" ]; then
  export GATEFORGE_PRIVATE_MODEL_ROOTS="$CURATED_ROOTS"
fi

python3 - "$PLAN_PATH" "$OUT_ROOT/problem_type_mapping_summary.json" <<'PY'
import json
import sys
from collections import defaultdict
from pathlib import Path

plan_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
plan = json.loads(plan_path.read_text(encoding="utf-8"))
rows = plan.get("plan_rows") if isinstance(plan.get("plan_rows"), list) else []

problem_to_exec = {
    "underconstrained_system": "model_check_error",
    "overconstrained_system": "constraint_violation",
    "undefined_symbol": "model_check_error",
    "connector_mismatch": "model_check_error",
    "array_dimension_mismatch": "model_check_error",
    "unit_inconsistency": "constraint_violation",
    "initialization_infeasible": "simulate_error",
    "event_logic_error": "simulate_error",
    "numerical_instability": "numerical_instability",
    "parameter_binding_error": "model_check_error",
    "sign_direction_error": "semantic_regression",
    "semantic_regression": "semantic_regression",
}

mapped_counts = defaultdict(int)
problem_type_targets = defaultdict(int)
exec_problem_type_targets = defaultdict(lambda: defaultdict(int))
unmapped = defaultdict(int)
for row in rows:
    if not isinstance(row, dict):
        continue
    ftype = str(row.get("failure_type") or "").strip().lower()
    target = int(row.get("target_mutant_count", 0) or 0)
    if ftype:
        problem_type_targets[ftype] += target
    if ftype in problem_to_exec:
        exec_ftype = problem_to_exec[ftype]
        mapped_counts[exec_ftype] += target
        exec_problem_type_targets[exec_ftype][ftype] += target
    else:
        unmapped[ftype] += target

exec_to_problem_types = {k: sorted(v.keys()) for k, v in exec_problem_type_targets.items()}
exec_problem_type_weights = {}
for exec_ftype, targets in exec_problem_type_targets.items():
    denom = sum(int(x) for x in targets.values())
    if denom <= 0:
        continue
    exec_problem_type_weights[exec_ftype] = {k: round(float(v) / float(denom), 6) for k, v in sorted(targets.items())}

payload = {
    "status": "PASS",
    "mapped_failure_type_targets": dict(sorted(mapped_counts.items())),
    "unmapped_problem_type_targets": dict(sorted(unmapped.items())),
    "mapping": problem_to_exec,
    "problem_type_targets": dict(sorted(problem_type_targets.items())),
    "exec_failure_type_problem_type_targets": {k: dict(sorted(v.items())) for k, v in sorted(exec_problem_type_targets.items())},
    "exec_to_problem_types": dict(sorted(exec_to_problem_types.items())),
    "exec_failure_type_problem_type_weights": dict(sorted(exec_problem_type_weights.items())),
}
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"status": "PASS", "mapped_failure_types": len(mapped_counts), "unmapped_problem_types": len(unmapped)}))
PY

phase_failure_types() {
  case "$1" in
    phase_check) echo "model_check_error,constraint_violation" ;;
    phase_sim) echo "simulate_error,numerical_instability" ;;
    phase_semantic) echo "semantic_regression" ;;
    *) echo "" ;;
  esac
}

phase_rc_any=0
phase_rows_json="$OUT_ROOT/phase_results.jsonl"
rm -f "$phase_rows_json"

for phase in phase_check phase_sim phase_semantic; do
  phase_out="$OUT_ROOT/$phase"
  mkdir -p "$phase_out"
  export GATEFORGE_PRIVATE_BATCH_OUT_DIR="$phase_out"
  export GATEFORGE_FAILURE_TYPES="$(phase_failure_types "$phase")"
  phase_log="$phase_out/run.log"

  set +e
  bash "$RUNNER_SCRIPT" >"$phase_log" 2>&1
  rc=$?
  set -e

  if [ "$rc" -ne 0 ]; then
    phase_rc_any=1
  fi

  python3 - "$phase_out" "$OUT_ROOT/problem_type_mapping_summary.json" <<'PY'
import json
import sys
from pathlib import Path

phase_out = Path(sys.argv[1])
mapping_path = Path(sys.argv[2])
manifest_path = phase_out / "mutation_manifest.json"
validation_records_path = phase_out / "mutation_validation_records.json"
out_path = phase_out / "problem_type_annotation_summary.json"

mapping = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.exists() else {}
reverse = mapping.get("exec_to_problem_types") if isinstance(mapping.get("exec_to_problem_types"), dict) else {}
weights = mapping.get("exec_failure_type_problem_type_weights") if isinstance(mapping.get("exec_failure_type_problem_type_weights"), dict) else {}


def _norm_failure_type(row: dict) -> str:
    for key in ("failure_type", "expected_failure_type", "actual_failure_type", "observed_failure_type"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return ""


def _annotate_row(row: dict) -> bool:
    ftype = _norm_failure_type(row)
    if not ftype:
        return False
    candidates = reverse.get(ftype) if isinstance(reverse.get(ftype), list) else []
    candidates = [str(x) for x in candidates if isinstance(x, str) and str(x).strip()]
    if candidates:
        row["problem_type_candidates"] = sorted(set(candidates))
    weight_row = weights.get(ftype) if isinstance(weights.get(ftype), dict) else {}
    if weight_row:
        row["problem_type_target_weights"] = {str(k): float(v) for k, v in sorted(weight_row.items())}
    if len(candidates) == 1:
        row["problem_type"] = str(candidates[0])
    row["failure_type_canonical"] = ftype
    return bool(candidates)


annotation_count = 0
manifest_rows = 0
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    for row in rows:
        if isinstance(row, dict):
            manifest_rows += 1
            if _annotate_row(row):
                annotation_count += 1
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

validation_rows = 0
if validation_records_path.exists():
    payload = json.loads(validation_records_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in ("mutation_records", "validated_records", "records"):
            rows = payload.get(key)
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        validation_rows += 1
                        _annotate_row(row)
    elif isinstance(payload, list):
        for row in payload:
            if isinstance(row, dict):
                validation_rows += 1
                _annotate_row(row)
    validation_records_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

summary = {
    "status": "PASS",
    "manifest_rows": manifest_rows,
    "validation_rows": validation_rows,
    "annotated_rows": annotation_count,
    "mapping_path": str(mapping_path),
    "manifest_path": str(manifest_path),
    "validation_records_path": str(validation_records_path),
}
out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"status": "PASS", "annotated_rows": annotation_count, "manifest_rows": manifest_rows}))
PY

  python3 - "$phase" "$phase_out" "$rc" "$phase_rows_json" <<'PY'
import json
import sys
from pathlib import Path

phase = sys.argv[1]
phase_out = Path(sys.argv[2])
rc = int(sys.argv[3])
rows_jsonl = Path(sys.argv[4])

summary_path = phase_out / "summary.json"
pack_path = phase_out / "mutation_pack_summary.json"
realrun_path = phase_out / "mutation_real_runner_summary.json"
validation_path = phase_out / "mutation_validation_summary.json"
problem_annotation_path = phase_out / "problem_type_annotation_summary.json"

summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
pack = json.loads(pack_path.read_text(encoding="utf-8")) if pack_path.exists() else {}
realrun = json.loads(realrun_path.read_text(encoding="utf-8")) if realrun_path.exists() else {}
validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}
problem_annotation = json.loads(problem_annotation_path.read_text(encoding="utf-8")) if problem_annotation_path.exists() else {}

row = {
    "phase": phase,
    "exit_code": rc,
    "bundle_status": str(summary.get("bundle_status") or ""),
    "mutation_pack_status": str(pack.get("status") or summary.get("mutation_pack_status") or ""),
    "realrun_status": str(realrun.get("status") or summary.get("mutation_realrun_status") or ""),
    "generated_mutations": int(summary.get("generated_mutations", 0) or 0),
    "reproducible_mutations": int(summary.get("reproducible_mutations", 0) or 0),
    "failure_types_count": int(summary.get("failure_types_count", 0) or 0),
    "validation_type_match_rate_pct": validation.get("type_match_rate_pct"),
    "validation_stage_match_rate_pct": validation.get("stage_match_rate_pct"),
    "validation_status": str(validation.get("status") or ""),
    "validation_backend_used": str(validation.get("validation_backend_used") or ""),
    "validation_backend_fallback_to_syntax": bool(validation.get("backend_fallback_to_syntax")),
    "baseline_check_pass_rate_pct": validation.get("baseline_check_pass_rate_pct"),
    "problem_type_annotation_status": str(problem_annotation.get("status") or ""),
    "problem_type_annotated_rows": int(problem_annotation.get("annotated_rows", 0) or 0),
    "paths": {
        "summary": str(summary_path),
        "mutation_pack_summary": str(pack_path),
        "mutation_real_runner_summary": str(realrun_path),
        "mutation_validation_summary": str(validation_path),
        "problem_type_annotation_summary": str(problem_annotation_path),
        "run_log": str(phase_out / "run.log"),
    },
}
with rows_jsonl.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row) + "\n")
print(json.dumps({"phase": phase, "exit_code": rc, "bundle_status": row["bundle_status"], "generated_mutations": row["generated_mutations"]}))
PY
done

python3 - "$phase_rows_json" "$OUT_ROOT/problem_type_mapping_summary.json" "$OUT_ROOT/summary.json" "$OUT_ROOT/summary.md" "$phase_rc_any" "$STRICT_OMC" "$STRICT_MIN_TYPE_MATCH_PCT" "$STRICT_MIN_STAGE_MATCH_PCT" <<'PY'
import json
import statistics
import sys
from pathlib import Path

rows_path = Path(sys.argv[1])
mapping_path = Path(sys.argv[2])
out_json = Path(sys.argv[3])
out_md = Path(sys.argv[4])
phase_rc_any = int(sys.argv[5])
strict_omc = str(sys.argv[6]).strip() == "1"
strict_min_type_match = float(sys.argv[7])
strict_min_stage_match = float(sys.argv[8])

rows = []
if rows_path.exists():
    for line in rows_path.read_text(encoding="utf-8").splitlines():
        text = str(line or "").strip()
        if not text:
            continue
        row = json.loads(text)
        if isinstance(row, dict):
            rows.append(row)
mapping = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.exists() else {}

generated = sum(int(r.get("generated_mutations", 0) or 0) for r in rows)
repro = sum(int(r.get("reproducible_mutations", 0) or 0) for r in rows)
bundle_pass = sum(1 for r in rows if str(r.get("bundle_status") or "") == "PASS")
type_rates = [float(r.get("validation_type_match_rate_pct")) for r in rows if isinstance(r.get("validation_type_match_rate_pct"), (int, float))]
stage_rates = [float(r.get("validation_stage_match_rate_pct")) for r in rows if isinstance(r.get("validation_stage_match_rate_pct"), (int, float))]
real_omc_backends = {"omc", "openmodelica_docker"}
validation_backend_mismatch = [
    r for r in rows if str(r.get("validation_backend_used") or "").strip().lower() not in real_omc_backends
]
validation_backend_fallback_rows = [
    r for r in rows if bool(r.get("validation_backend_fallback_to_syntax"))
]
baseline_zero_rows = [
    r
    for r in rows
    if not isinstance(r.get("baseline_check_pass_rate_pct"), (int, float))
    or float(r.get("baseline_check_pass_rate_pct")) <= 0.0
]
validation_low_type_rows = [
    r
    for r in rows
    if not isinstance(r.get("validation_type_match_rate_pct"), (int, float))
    or float(r.get("validation_type_match_rate_pct")) < strict_min_type_match
]
validation_low_stage_rows = [
    r
    for r in rows
    if not isinstance(r.get("validation_stage_match_rate_pct"), (int, float))
    or float(r.get("validation_stage_match_rate_pct")) < strict_min_stage_match
]
problem_type_annotation_missing_rows = [
    r for r in rows if str(r.get("problem_type_annotation_status") or "") != "PASS" or int(r.get("problem_type_annotated_rows", 0) or 0) <= 0
]

status = "PASS"
reasons = []
if phase_rc_any != 0:
    status = "NEEDS_REVIEW"
    reasons.append("one_or_more_phases_nonzero_exit")
if bundle_pass < len(rows):
    status = "NEEDS_REVIEW"
    reasons.append("one_or_more_phase_bundle_not_pass")
if generated <= 0:
    status = "FAIL"
    reasons.append("generated_mutations_zero")
if strict_omc and validation_backend_mismatch:
    status = "FAIL"
    reasons.append("validation_backend_not_real_omc")
if strict_omc and validation_backend_fallback_rows:
    status = "FAIL"
    reasons.append("validation_backend_fallback_to_syntax")
if strict_omc and baseline_zero_rows and len(baseline_zero_rows) == len(rows):
    status = "FAIL"
    reasons.append("validation_baseline_check_pass_rate_zero_all_phases")
if strict_omc and validation_low_type_rows:
    status = "FAIL"
    reasons.append("validation_type_match_rate_below_strict_threshold")
if strict_omc and validation_low_stage_rows:
    status = "FAIL"
    reasons.append("validation_stage_match_rate_below_strict_threshold")
if problem_type_annotation_missing_rows:
    status = "FAIL"
    reasons.append("problem_type_annotation_missing")

payload = {
    "status": status,
    "phase_count": len(rows),
    "phase_rows": rows,
    "generated_mutations_total": generated,
    "reproducible_mutations_total": repro,
    "median_validation_type_match_rate_pct": round(statistics.median(type_rates), 4) if type_rates else None,
    "median_validation_stage_match_rate_pct": round(statistics.median(stage_rates), 4) if stage_rates else None,
    "problem_type_mapping_summary": mapping,
    "strict_omc": strict_omc,
    "strict_min_type_match_rate_pct": strict_min_type_match,
    "strict_min_stage_match_rate_pct": strict_min_stage_match,
    "validation_backend_not_omc_phase_count": len(validation_backend_mismatch),
    "validation_backend_fallback_phase_count": len(validation_backend_fallback_rows),
    "baseline_zero_phase_count": len(baseline_zero_rows),
    "validation_low_type_match_phase_count": len(validation_low_type_rows),
    "validation_low_stage_match_phase_count": len(validation_low_stage_rows),
    "problem_type_annotation_missing_phase_count": len(problem_type_annotation_missing_rows),
    "reasons": reasons,
}
out_json.parent.mkdir(parents=True, exist_ok=True)
out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

lines = [
    "# Agent Modelica Problem Plan Execution v1",
    "",
    f"- status: `{status}`",
    f"- phase_count: `{len(rows)}`",
    f"- generated_mutations_total: `{generated}`",
    f"- reproducible_mutations_total: `{repro}`",
    f"- median_validation_type_match_rate_pct: `{payload.get('median_validation_type_match_rate_pct')}`",
    f"- median_validation_stage_match_rate_pct: `{payload.get('median_validation_stage_match_rate_pct')}`",
    f"- strict_min_type_match_rate_pct: `{strict_min_type_match}`",
    f"- strict_min_stage_match_rate_pct: `{strict_min_stage_match}`",
    "",
    "## Per Phase",
    "",
]
for row in rows:
    lines.append(
        f"- {row.get('phase')}: exit=`{row.get('exit_code')}` bundle=`{row.get('bundle_status')}` generated=`{row.get('generated_mutations')}` reproducible=`{row.get('reproducible_mutations')}`"
    )
lines.append("")
out_md.write_text("\n".join(lines), encoding="utf-8")
print(
    json.dumps(
        {
            "status": status,
            "phase_count": len(rows),
            "generated_mutations_total": generated,
            "reasons": reasons,
        }
    )
)
if status == "FAIL":
    raise SystemExit(1)
PY
