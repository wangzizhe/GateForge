#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/repair_orchestrate_compare_demo

cat > artifacts/repair_orchestrate_compare_demo/source_fail.json <<'JSON'
{
  "proposal_id": "repair-orchestrate-compare-demo-001",
  "status": "FAIL",
  "policy_decision": "FAIL",
  "risk_level": "medium",
  "policy_reasons": [
    "runtime_regression:1.3s>1.0s",
    "performance_regression_detected"
  ],
  "fail_reasons": [
    "regression_fail"
  ]
}
JSON

python3 -m gateforge.repair_orchestrate \
  --source artifacts/repair_orchestrate_compare_demo/source_fail.json \
  --planner-backend rule \
  --compare-strategy-profiles default industrial_strict \
  --baseline baselines/mock_minimal_probe_baseline.json \
  --out-dir artifacts/repair_orchestrate_compare_demo \
  --out artifacts/repair_orchestrate_compare_demo/summary.json

cat artifacts/repair_orchestrate_compare_demo/summary.json

python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("artifacts/repair_orchestrate_compare_demo/summary.json").read_text(encoding="utf-8"))
compare = summary.get("strategy_compare", {})
flags = {
    "expect_compare_present": "PASS" if isinstance(summary.get("compare"), dict) else "FAIL",
    "expect_profiles_match": "PASS"
    if compare.get("from_profile") == "default" and compare.get("to_profile") == "industrial_strict"
    else "FAIL",
    "expect_primary_status_pass": "PASS" if summary.get("primary", {}).get("status") == "PASS" else "FAIL",
    "expect_compare_status_pass": "PASS" if summary.get("compare", {}).get("status") == "PASS" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "status": summary.get("status"),
    "primary_batch_status": summary.get("primary", {}).get("batch_status"),
    "compare_batch_status": summary.get("compare", {}).get("batch_status"),
    "compare_relation": compare.get("relation"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
Path("artifacts/repair_orchestrate_compare_demo/demo_summary.json").write_text(
    json.dumps(demo, indent=2), encoding="utf-8"
)
Path("artifacts/repair_orchestrate_compare_demo/demo_summary.md").write_text(
    "\n".join(
        [
            "# Repair Orchestrate Compare Demo",
            "",
            f"- status: `{demo['status']}`",
            f"- primary_batch_status: `{demo['primary_batch_status']}`",
            f"- compare_batch_status: `{demo['compare_batch_status']}`",
            f"- compare_relation: `{demo['compare_relation']}`",
            f"- bundle_status: `{demo['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- expect_compare_present: `{flags['expect_compare_present']}`",
            f"- expect_profiles_match: `{flags['expect_profiles_match']}`",
            f"- expect_primary_status_pass: `{flags['expect_primary_status_pass']}`",
            f"- expect_compare_status_pass: `{flags['expect_compare_status_pass']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/repair_orchestrate_compare_demo/demo_summary.json
cat artifacts/repair_orchestrate_compare_demo/demo_summary.md
