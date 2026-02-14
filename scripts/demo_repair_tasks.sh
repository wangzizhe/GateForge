#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/repair_tasks_demo

cat > artifacts/repair_tasks_demo/source_fail.json <<'JSON'
{
  "proposal_id": "repair-tasks-demo-001",
  "status": "FAIL",
  "policy_decision": "FAIL",
  "risk_level": "medium",
  "policy_reasons": [
    "runtime_regression:1.3s>1.0s",
    "performance_regression_detected"
  ],
  "fail_reasons": [
    "regression_fail"
  ],
  "candidate_path": "artifacts/candidate_from_proposal.json",
  "regression_path": "artifacts/regression_from_proposal.json"
}
JSON

python3 -m gateforge.repair_tasks \
  --source artifacts/repair_tasks_demo/source_fail.json \
  --out artifacts/repair_tasks_demo/summary.json \
  --report artifacts/repair_tasks_demo/summary.md

cat artifacts/repair_tasks_demo/summary.json
cat artifacts/repair_tasks_demo/summary.md

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/repair_tasks_demo/summary.json").read_text(encoding="utf-8"))
flags = {
    "expect_policy_decision_fail": "PASS" if payload.get("policy_decision") == "FAIL" else "FAIL",
    "expect_task_count_positive": "PASS" if payload.get("task_count", 0) > 0 else "FAIL",
    "expect_runtime_reason_present": "PASS" if any("runtime_regression" in r for r in payload.get("policy_reasons", [])) else "FAIL",
    "expect_p0_present": "PASS" if int((payload.get("priority_counts") or {}).get("P0", 0)) > 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "policy_decision": payload.get("policy_decision"),
    "task_count": payload.get("task_count"),
    "p0_count": int((payload.get("priority_counts") or {}).get("P0", 0)),
    "result_flags": flags,
    "bundle_status": bundle_status
}
Path("artifacts/repair_tasks_demo/demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
Path("artifacts/repair_tasks_demo/demo_summary.md").write_text(
    "\n".join(
        [
            "# Repair Tasks Demo",
            "",
            f"- policy_decision: `{summary['policy_decision']}`",
            f"- task_count: `{summary['task_count']}`",
            f"- p0_count: `{summary['p0_count']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- expect_policy_decision_fail: `{flags['expect_policy_decision_fail']}`",
            f"- expect_task_count_positive: `{flags['expect_task_count_positive']}`",
            f"- expect_runtime_reason_present: `{flags['expect_runtime_reason_present']}`",
            f"- expect_p0_present: `{flags['expect_p0_present']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
