#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/repair_orchestrate_demo

cat > artifacts/repair_orchestrate_demo/source_fail.json <<'JSON'
{
  "proposal_id": "repair-orchestrate-demo-001",
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

python3 -m gateforge.repair_orchestrate \
  --source artifacts/repair_orchestrate_demo/source_fail.json \
  --planner-backend rule \
  --strategy-profile default \
  --baseline baselines/mock_minimal_probe_baseline.json \
  --out-dir artifacts/repair_orchestrate_demo \
  --out artifacts/repair_orchestrate_demo/summary.json

cat artifacts/repair_orchestrate_demo/summary.json
cat artifacts/repair_orchestrate_demo/tasks.json
cat artifacts/repair_orchestrate_demo/pack.json
cat artifacts/repair_orchestrate_demo/batch_summary.json

python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("artifacts/repair_orchestrate_demo/summary.json").read_text(encoding="utf-8"))
batch = json.loads(Path("artifacts/repair_orchestrate_demo/batch_summary.json").read_text(encoding="utf-8"))
flags = {
    "expect_status_pass": "PASS" if summary.get("status") == "PASS" else "FAIL",
    "expect_steps_ok": "PASS" if all(v == 0 for v in summary.get("step_exit_codes", {}).values()) else "FAIL",
    "expect_pack_cases_positive": "PASS" if batch.get("total_cases", 0) > 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "status": summary.get("status"),
    "strategy_profile": summary.get("strategy_profile"),
    "total_cases": batch.get("total_cases"),
    "pass_count": batch.get("pass_count"),
    "fail_count": batch.get("fail_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
Path("artifacts/repair_orchestrate_demo/demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
Path("artifacts/repair_orchestrate_demo/demo_summary.md").write_text(
    "\n".join(
        [
            "# Repair Orchestrate Demo",
            "",
            f"- status: `{demo['status']}`",
            f"- strategy_profile: `{demo['strategy_profile']}`",
            f"- total_cases: `{demo['total_cases']}`",
            f"- pass_count: `{demo['pass_count']}`",
            f"- fail_count: `{demo['fail_count']}`",
            f"- bundle_status: `{demo['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- expect_status_pass: `{flags['expect_status_pass']}`",
            f"- expect_steps_ok: `{flags['expect_steps_ok']}`",
            f"- expect_pack_cases_positive: `{flags['expect_pack_cases_positive']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/repair_orchestrate_demo/demo_summary.json
cat artifacts/repair_orchestrate_demo/demo_summary.md
