#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/agent_modelica_mutation_plan_builder_v1_demo"
mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_mutation_plan_builder_v1 \
  --taxonomy benchmarks/agent_modelica_problem_taxonomy_v1.json \
  --quota-profile benchmarks/agent_modelica_problem_quota_v1.json \
  --plan-out "$OUT_DIR/plan.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/agent_modelica_mutation_plan_builder_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
rows = plan.get("plan_rows") if isinstance(plan.get("plan_rows"), list) else []
flags = {
    "status_valid": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
    "rows_present": "PASS" if len(rows) >= 1 else "FAIL",
    "failure_type_coverage": "PASS" if int(summary.get("failure_type_count", 0) or 0) >= 10 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "bundle_status": bundle_status,
    "mutation_plan_status": summary.get("status"),
    "total_plan_rows": summary.get("total_plan_rows"),
    "total_target_mutants": summary.get("total_target_mutants"),
    "failure_type_count": summary.get("failure_type_count"),
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "mutation_plan_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
