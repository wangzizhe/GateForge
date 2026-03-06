#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PLAN_PATH="${GATEFORGE_AGENT_PROBLEM_PLAN_PATH:-artifacts/agent_modelica_mutation_plan_builder_v1_demo/plan.json}"
OUT_ROOT="${GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_OUT_DIR:-artifacts/agent_modelica_problem_plan_execution_v1}"
RUNNER_SCRIPT="${GATEFORGE_AGENT_MUTATION_BATCH_RUNNER:-scripts/run_private_model_mutation_scale_batch_v1.sh}"
EXECUTION_PROFILE="${GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_PROFILE:-quick}"

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
  DEFAULT_MIN_GENERATED_MUTATIONS="6"
  DEFAULT_MAX_MUTATION_MODELS="24"
fi

MUTATIONS_PER_FAILURE_TYPE="${GATEFORGE_MUTATIONS_PER_FAILURE_TYPE:-$DEFAULT_MUTATIONS_PER_FAILURE_TYPE}"
MIN_GENERATED_MUTATIONS="${GATEFORGE_MIN_GENERATED_MUTATIONS:-$DEFAULT_MIN_GENERATED_MUTATIONS}"
MAX_MUTATION_MODELS="${GATEFORGE_MAX_MUTATION_MODELS:-$DEFAULT_MAX_MUTATION_MODELS}"
TARGET_SCALES="${GATEFORGE_TARGET_SCALES:-small,medium,large}"
VALIDATION_MAX_MUTATIONS="${GATEFORGE_MUTATION_VALIDATION_MAX_MUTATIONS:-300}"
VALIDATION_MAX_BASELINES="${GATEFORGE_MUTATION_VALIDATION_MAX_BASELINES:-120}"

export GATEFORGE_MUTATIONS_PER_FAILURE_TYPE="$MUTATIONS_PER_FAILURE_TYPE"
export GATEFORGE_MIN_GENERATED_MUTATIONS="$MIN_GENERATED_MUTATIONS"
export GATEFORGE_MAX_MUTATION_MODELS="$MAX_MUTATION_MODELS"
export GATEFORGE_TARGET_SCALES="$TARGET_SCALES"
export GATEFORGE_MUTATION_VALIDATION_MAX_MUTATIONS="$VALIDATION_MAX_MUTATIONS"
export GATEFORGE_MUTATION_VALIDATION_MAX_BASELINES="$VALIDATION_MAX_BASELINES"
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
unmapped = defaultdict(int)
for row in rows:
    if not isinstance(row, dict):
        continue
    ftype = str(row.get("failure_type") or "").strip().lower()
    target = int(row.get("target_mutant_count", 0) or 0)
    if ftype in problem_to_exec:
        mapped_counts[problem_to_exec[ftype]] += target
    else:
        unmapped[ftype] += target

payload = {
    "status": "PASS",
    "mapped_failure_type_targets": dict(sorted(mapped_counts.items())),
    "unmapped_problem_type_targets": dict(sorted(unmapped.items())),
    "mapping": problem_to_exec,
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

summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
pack = json.loads(pack_path.read_text(encoding="utf-8")) if pack_path.exists() else {}
realrun = json.loads(realrun_path.read_text(encoding="utf-8")) if realrun_path.exists() else {}
validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}

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
    "paths": {
        "summary": str(summary_path),
        "mutation_pack_summary": str(pack_path),
        "mutation_real_runner_summary": str(realrun_path),
        "mutation_validation_summary": str(validation_path),
        "run_log": str(phase_out / "run.log"),
    },
}
with rows_jsonl.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row) + "\n")
print(json.dumps({"phase": phase, "exit_code": rc, "bundle_status": row["bundle_status"], "generated_mutations": row["generated_mutations"]}))
PY
done

python3 - "$phase_rows_json" "$OUT_ROOT/problem_type_mapping_summary.json" "$OUT_ROOT/summary.json" "$OUT_ROOT/summary.md" "$phase_rc_any" <<'PY'
import json
import statistics
import sys
from pathlib import Path

rows_path = Path(sys.argv[1])
mapping_path = Path(sys.argv[2])
out_json = Path(sys.argv[3])
out_md = Path(sys.argv[4])
phase_rc_any = int(sys.argv[5])

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

payload = {
    "status": status,
    "phase_count": len(rows),
    "phase_rows": rows,
    "generated_mutations_total": generated,
    "reproducible_mutations_total": repro,
    "median_validation_type_match_rate_pct": round(statistics.median(type_rates), 4) if type_rates else None,
    "problem_type_mapping_summary": mapping,
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
print(json.dumps({"status": status, "phase_count": len(rows), "generated_mutations_total": generated}))
if status == "FAIL":
    raise SystemExit(1)
PY
