#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/repair_batch_compare_demo

cat > artifacts/repair_batch_compare_demo/source_recover.json <<'JSON'
{
  "proposal_id": "repair-batch-compare-recover-001",
  "status": "FAIL",
  "policy_decision": "FAIL",
  "policy_reasons": [
    "runtime_regression:1.2s>1.0s"
  ],
  "fail_reasons": [
    "regression_fail"
  ]
}
JSON

cat > artifacts/repair_batch_compare_demo/source_worse.json <<'JSON'
{
  "proposal_id": "repair-batch-compare-worse-001",
  "status": "PASS",
  "policy_decision": "PASS",
  "policy_reasons": [],
  "fail_reasons": []
}
JSON

cat > artifacts/repair_batch_compare_demo/pack.json <<'JSON'
{
  "pack_id": "repair_batch_compare_demo_v0",
  "cases": [
    {
      "name": "recover_case",
      "source": "artifacts/repair_batch_compare_demo/source_recover.json",
      "baseline": "baselines/mock_minimal_probe_baseline.json",
      "planner_backend": "rule"
    },
    {
      "name": "worse_case",
      "source": "artifacts/repair_batch_compare_demo/source_worse.json",
      "baseline": "baselines/openmodelica_minimal_probe_baseline.json",
      "planner_backend": "rule"
    }
  ]
}
JSON

set +e
python3 -m gateforge.repair_batch \
  --pack artifacts/repair_batch_compare_demo/pack.json \
  --compare-policy-profiles default industrial_strict_v0 \
  --continue-on-fail \
  --summary-out artifacts/repair_batch_compare_demo/summary.json \
  --report-out artifacts/repair_batch_compare_demo/summary.md
set -e

cat artifacts/repair_batch_compare_demo/summary.json
cat artifacts/repair_batch_compare_demo/summary.md

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/repair_batch_compare_demo/summary.json").read_text(encoding="utf-8"))
compare = payload.get("profile_compare", {})
result_flags = {
    "expect_compare_present": "PASS" if isinstance(compare, dict) and compare else "FAIL",
    "expect_total_compared_cases": "PASS" if compare.get("total_compared_cases") == 2 else "FAIL",
    "expect_rate_present": "PASS" if "strict_downgrade_rate" in compare else "FAIL",
    "expect_reason_distribution_present": "PASS" if isinstance(compare.get("reason_distribution"), dict) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in result_flags.values()) else "FAIL"
summary = {
    "pack_id": payload.get("pack_id"),
    "total_cases": payload.get("total_cases"),
    "compare": {
        "from_policy_profile": compare.get("from_policy_profile"),
        "to_policy_profile": compare.get("to_policy_profile"),
        "total_compared_cases": compare.get("total_compared_cases"),
        "strict_downgrade_rate": compare.get("strict_downgrade_rate"),
    },
    "result_flags": result_flags,
    "bundle_status": bundle_status,
}
Path("artifacts/repair_batch_compare_demo/demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
lines = [
    "# Repair Batch Compare Demo",
    "",
    f"- pack_id: `{summary['pack_id']}`",
    f"- total_cases: `{summary['total_cases']}`",
    f"- from_policy_profile: `{summary['compare']['from_policy_profile']}`",
    f"- to_policy_profile: `{summary['compare']['to_policy_profile']}`",
    f"- total_compared_cases: `{summary['compare']['total_compared_cases']}`",
    f"- strict_downgrade_rate: `{summary['compare']['strict_downgrade_rate']}`",
    f"- bundle_status: `{summary['bundle_status']}`",
    "",
    "## Result Flags",
    "",
]
for k, v in result_flags.items():
    lines.append(f"- {k}: `{v}`")
Path("artifacts/repair_batch_compare_demo/demo_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/repair_batch_compare_demo/demo_summary.json
cat artifacts/repair_batch_compare_demo/demo_summary.md
