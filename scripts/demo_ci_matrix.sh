#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Local matrix that simulates workflow_dispatch optional jobs.
# Defaults: run demos, skip benchmark (to keep loop fast).
RUN_CHECKER_DEMO="${RUN_CHECKER_DEMO:-1}"
RUN_STEADY_STATE_DEMO="${RUN_STEADY_STATE_DEMO:-1}"
RUN_BEHAVIOR_METRICS_DEMO="${RUN_BEHAVIOR_METRICS_DEMO:-1}"
RUN_DEMO_BUNDLE="${RUN_DEMO_BUNDLE:-1}"
RUN_AUTOPILOT_DRY_RUN="${RUN_AUTOPILOT_DRY_RUN:-1}"
RUN_AGENT_CHANGE_LOOP="${RUN_AGENT_CHANGE_LOOP:-1}"
RUN_REPAIR_LOOP="${RUN_REPAIR_LOOP:-1}"
RUN_PLANNER_GUARDRAILS="${RUN_PLANNER_GUARDRAILS:-1}"
RUN_REPAIR_BATCH_DEMO="${RUN_REPAIR_BATCH_DEMO:-1}"
RUN_REPAIR_BATCH_COMPARE_DEMO="${RUN_REPAIR_BATCH_COMPARE_DEMO:-1}"
RUN_GOVERNANCE_SNAPSHOT_DEMO="${RUN_GOVERNANCE_SNAPSHOT_DEMO:-1}"
RUN_BENCHMARK="${RUN_BENCHMARK:-0}"
POLICY_PROFILE="${POLICY_PROFILE:-}"
export RUN_CHECKER_DEMO RUN_STEADY_STATE_DEMO RUN_BEHAVIOR_METRICS_DEMO RUN_DEMO_BUNDLE RUN_AUTOPILOT_DRY_RUN RUN_AGENT_CHANGE_LOOP RUN_REPAIR_LOOP RUN_PLANNER_GUARDRAILS RUN_REPAIR_BATCH_DEMO RUN_REPAIR_BATCH_COMPARE_DEMO RUN_GOVERNANCE_SNAPSHOT_DEMO RUN_BENCHMARK POLICY_PROFILE

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      RUN_CHECKER_DEMO=1
      RUN_STEADY_STATE_DEMO=1
      RUN_BEHAVIOR_METRICS_DEMO=1
      RUN_DEMO_BUNDLE=1
      RUN_AUTOPILOT_DRY_RUN=1
      RUN_AGENT_CHANGE_LOOP=1
      RUN_REPAIR_LOOP=1
      RUN_PLANNER_GUARDRAILS=1
      RUN_REPAIR_BATCH_DEMO=1
      RUN_REPAIR_BATCH_COMPARE_DEMO=1
      RUN_GOVERNANCE_SNAPSHOT_DEMO=1
      shift
      ;;
    --none)
      RUN_CHECKER_DEMO=0
      RUN_STEADY_STATE_DEMO=0
      RUN_BEHAVIOR_METRICS_DEMO=0
      RUN_DEMO_BUNDLE=0
      RUN_AUTOPILOT_DRY_RUN=0
      RUN_AGENT_CHANGE_LOOP=0
      RUN_REPAIR_LOOP=0
      RUN_PLANNER_GUARDRAILS=0
      RUN_REPAIR_BATCH_DEMO=0
      RUN_REPAIR_BATCH_COMPARE_DEMO=0
      RUN_GOVERNANCE_SNAPSHOT_DEMO=0
      RUN_BENCHMARK=0
      shift
      ;;
    --checker-demo)
      RUN_CHECKER_DEMO=1
      shift
      ;;
    --steady-state-demo)
      RUN_STEADY_STATE_DEMO=1
      shift
      ;;
    --behavior-metrics-demo)
      RUN_BEHAVIOR_METRICS_DEMO=1
      shift
      ;;
    --demo-bundle)
      RUN_DEMO_BUNDLE=1
      shift
      ;;
    --autopilot-dry-run)
      RUN_AUTOPILOT_DRY_RUN=1
      shift
      ;;
    --agent-change-loop)
      RUN_AGENT_CHANGE_LOOP=1
      shift
      ;;
    --repair-loop)
      RUN_REPAIR_LOOP=1
      shift
      ;;
    --planner-guardrails)
      RUN_PLANNER_GUARDRAILS=1
      shift
      ;;
    --repair-batch-demo)
      RUN_REPAIR_BATCH_DEMO=1
      shift
      ;;
    --repair-batch-compare-demo)
      RUN_REPAIR_BATCH_COMPARE_DEMO=1
      shift
      ;;
    --governance-snapshot-demo)
      RUN_GOVERNANCE_SNAPSHOT_DEMO=1
      shift
      ;;
    --benchmark)
      RUN_BENCHMARK=1
      shift
      ;;
    --policy-profile)
      POLICY_PROFILE="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

mkdir -p artifacts
mkdir -p artifacts/ci_matrix_logs

run_job() {
  local name="$1"
  shift
  local log_path="artifacts/ci_matrix_logs/${name}.log"
  set +e
  "$@" >"$log_path" 2>&1
  local code=$?
  set -e
  echo "$name:$code"
}

RESULTS=()
if [[ "$RUN_CHECKER_DEMO" == "1" ]]; then
  RESULTS+=("$(run_job checker_demo bash scripts/demo_checker_config.sh)")
fi
if [[ "$RUN_STEADY_STATE_DEMO" == "1" ]]; then
  RESULTS+=("$(run_job steady_state_demo bash scripts/demo_steady_state_checker.sh)")
fi
if [[ "$RUN_BEHAVIOR_METRICS_DEMO" == "1" ]]; then
  RESULTS+=("$(run_job behavior_metrics_demo bash scripts/demo_behavior_metrics_checker.sh)")
fi
if [[ "$RUN_DEMO_BUNDLE" == "1" ]]; then
  RESULTS+=("$(run_job demo_bundle bash scripts/demo_all.sh)")
fi
if [[ "$RUN_AUTOPILOT_DRY_RUN" == "1" ]]; then
  RESULTS+=("$(run_job autopilot_dry_run bash scripts/demo_autopilot_dry_run.sh)")
fi
if [[ "$RUN_AGENT_CHANGE_LOOP" == "1" ]]; then
  RESULTS+=("$(run_job agent_change_loop bash scripts/demo_agent_change_loop.sh)")
fi
if [[ "$RUN_REPAIR_LOOP" == "1" ]]; then
  RESULTS+=("$(run_job repair_loop bash scripts/demo_repair_loop.sh)")
fi
if [[ "$RUN_PLANNER_GUARDRAILS" == "1" ]]; then
  RESULTS+=("$(run_job planner_guardrails bash scripts/demo_planner_guardrails.sh)")
fi
if [[ "$RUN_REPAIR_BATCH_DEMO" == "1" ]]; then
  RESULTS+=("$(run_job repair_batch_demo bash scripts/demo_repair_batch.sh)")
fi
if [[ "$RUN_REPAIR_BATCH_COMPARE_DEMO" == "1" ]]; then
  RESULTS+=("$(run_job repair_batch_compare_demo bash scripts/demo_repair_batch_compare.sh)")
fi
if [[ "$RUN_GOVERNANCE_SNAPSHOT_DEMO" == "1" ]]; then
  RESULTS+=("$(run_job governance_snapshot_demo bash scripts/demo_governance_snapshot.sh)")
fi
if [[ "$RUN_BENCHMARK" == "1" ]]; then
  RESULTS+=("$(run_job benchmark python3 -m gateforge.benchmark --pack benchmarks/pack_v0.json --out-dir artifacts/benchmark_v0 --summary-out artifacts/benchmark_v0/summary.json --report-out artifacts/benchmark_v0/summary.md)")
fi

printf "%s\n" "${RESULTS[@]}" > artifacts/ci_matrix_results.tmp

python3 - <<'PY'
import json
import os
from pathlib import Path

selected = {
    "checker_demo": os.getenv("RUN_CHECKER_DEMO") == "1",
    "steady_state_demo": os.getenv("RUN_STEADY_STATE_DEMO") == "1",
    "behavior_metrics_demo": os.getenv("RUN_BEHAVIOR_METRICS_DEMO") == "1",
    "demo_bundle": os.getenv("RUN_DEMO_BUNDLE") == "1",
    "autopilot_dry_run": os.getenv("RUN_AUTOPILOT_DRY_RUN") == "1",
    "agent_change_loop": os.getenv("RUN_AGENT_CHANGE_LOOP") == "1",
    "repair_loop": os.getenv("RUN_REPAIR_LOOP") == "1",
    "planner_guardrails": os.getenv("RUN_PLANNER_GUARDRAILS") == "1",
    "repair_batch_demo": os.getenv("RUN_REPAIR_BATCH_DEMO") == "1",
    "repair_batch_compare_demo": os.getenv("RUN_REPAIR_BATCH_COMPARE_DEMO") == "1",
    "governance_snapshot_demo": os.getenv("RUN_GOVERNANCE_SNAPSHOT_DEMO") == "1",
    "benchmark": os.getenv("RUN_BENCHMARK") == "1",
}

results_path = Path("artifacts/ci_matrix_results.tmp")
results_raw = results_path.read_text(encoding="utf-8").strip().splitlines() if results_path.exists() else []
job_exit_codes: dict[str, int] = {}
for line in results_raw:
    if ":" not in line:
        continue
    n, c = line.split(":", 1)
    try:
        job_exit_codes[n] = int(c)
    except ValueError:
        job_exit_codes[n] = 99

selected_jobs = [k for k, v in selected.items() if v]
failed_jobs = [k for k in selected_jobs if job_exit_codes.get(k, 99) != 0]
matrix_status = "PASS" if not failed_jobs else "FAIL"

summary = {
    "matrix_status": matrix_status,
    "policy_profile": os.getenv("POLICY_PROFILE") or "default",
    "selected": selected,
    "selected_count": len(selected_jobs),
    "job_exit_codes": job_exit_codes,
    "failed_jobs": failed_jobs,
}

planner_guardrail_rule_ids = []
if selected.get("planner_guardrails"):
    guardrail_summary = Path("artifacts/planner_guardrails_demo/summary.json")
    if guardrail_summary.exists():
        payload = json.loads(guardrail_summary.read_text(encoding="utf-8"))
        rule_ids = payload.get("rule_ids", {}).get("all", [])
        if isinstance(rule_ids, list):
            planner_guardrail_rule_ids = [x for x in rule_ids if isinstance(x, str)]
summary["planner_guardrail_rule_ids"] = sorted(set(planner_guardrail_rule_ids))

out_json = Path("artifacts/ci_matrix_summary.json")
out_md = Path("artifacts/ci_matrix_summary.md")
out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

lines = [
    "# GateForge Local CI Matrix Summary",
    "",
    f"- matrix_status: `{summary['matrix_status']}`",
    f"- policy_profile: `{summary['policy_profile']}`",
    f"- selected_count: `{summary['selected_count']}`",
    "",
    "## Selected Jobs",
    "",
]
for name, enabled in selected.items():
    lines.append(f"- {name}: `{enabled}`")

lines.extend(["", "## Job Exit Codes", ""])
for name in sorted(job_exit_codes.keys()):
    lines.append(f"- {name}: `{job_exit_codes[name]}`")

lines.extend(["", "## Failed Jobs", ""])
if failed_jobs:
    for name in failed_jobs:
        lines.append(f"- {name}")
else:
    lines.append("- `none`")

lines.extend(["", "## Planner Guardrail Rule IDs", ""])
if summary["planner_guardrail_rule_ids"]:
    for rid in summary["planner_guardrail_rule_ids"]:
        lines.append(f"- {rid}")
else:
    lines.append("- `none`")

out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"matrix_status": matrix_status, "failed_jobs": failed_jobs}))
PY

rm -f artifacts/ci_matrix_results.tmp

if [[ -f artifacts/ci_matrix_summary.json ]]; then
  cat artifacts/ci_matrix_summary.json
fi
if [[ -f artifacts/ci_matrix_summary.md ]]; then
  cat artifacts/ci_matrix_summary.md
fi

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/ci_matrix_summary.json").read_text(encoding="utf-8"))
if payload.get("matrix_status") != "PASS":
    raise SystemExit(1)
PY
