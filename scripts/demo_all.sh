#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts

set +e
bash scripts/demo_proposal_flow.sh
FLOW_EXIT_CODE=$?
bash scripts/demo_checker_config.sh
CHECKER_EXIT_CODE=$?
set -e

export GATEFORGE_FLOW_EXIT_CODE="$FLOW_EXIT_CODE"
export GATEFORGE_CHECKER_EXIT_CODE="$CHECKER_EXIT_CODE"

python3 - <<'PY'
import json
import os
from pathlib import Path
from gateforge.demo_bundle import validate_demo_bundle_summary

def read_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))

proposal = read_json("artifacts/proposal_run_demo.json")
checker = read_json("artifacts/checker_demo_run.json")
flow_exit = int(os.getenv("GATEFORGE_FLOW_EXIT_CODE", "-1"))
checker_exit = int(os.getenv("GATEFORGE_CHECKER_EXIT_CODE", "-1"))

lines = [
    "# GateForge Demo Bundle Summary",
    "",
    f"- flow_exit_code: `{flow_exit}`",
    f"- checker_exit_code: `{checker_exit}`",
    f"- proposal_flow_status: `{proposal.get('status')}`",
    f"- checker_demo_status: `{checker.get('status')}`",
    f"- checker_demo_policy_decision: `{checker.get('policy_decision')}`",
    "",
    "## Result Flags",
    "",
    f"- proposal_flow: `{'PASS' if proposal.get('status') == 'PASS' else 'FAIL'}`",
    f"- checker_demo_expected_fail: `{'PASS' if checker.get('status') == 'FAIL' else 'FAIL'}`",
    "",
    "## Key Artifacts",
    "",
    "- `artifacts/proposal_run_demo.json`",
    "- `artifacts/proposal_run_demo.md`",
    "- `artifacts/regression_from_proposal_demo.json`",
    "- `artifacts/checker_demo_run.json`",
    "- `artifacts/checker_demo_regression.json`",
    "- `artifacts/checker_demo_summary.md`",
    "",
]

summary_json = {
    "flow_exit_code": flow_exit,
    "checker_exit_code": checker_exit,
    "proposal_flow_status": proposal.get("status"),
    "checker_demo_status": checker.get("status"),
    "checker_demo_policy_decision": checker.get("policy_decision"),
    "result_flags": {
        "proposal_flow": "PASS" if proposal.get("status") == "PASS" else "FAIL",
        "checker_demo_expected_fail": "PASS" if checker.get("status") == "FAIL" else "FAIL",
    },
    "artifacts": [
        "artifacts/proposal_run_demo.json",
        "artifacts/proposal_run_demo.md",
        "artifacts/regression_from_proposal_demo.json",
        "artifacts/checker_demo_run.json",
        "artifacts/checker_demo_regression.json",
        "artifacts/checker_demo_summary.md",
        "artifacts/demo_all_summary.md",
        "artifacts/demo_all_summary.json",
    ],
}
bundle_status = "PASS"
if summary_json["result_flags"]["proposal_flow"] != "PASS":
    bundle_status = "FAIL"
if summary_json["result_flags"]["checker_demo_expected_fail"] != "PASS":
    bundle_status = "FAIL"
summary_json["bundle_status"] = bundle_status
validate_demo_bundle_summary(summary_json)

lines.insert(10, f"- bundle_status: `{bundle_status}`")

Path("artifacts/demo_all_summary.md").write_text("\n".join(lines), encoding="utf-8")
Path("artifacts/demo_all_summary.json").write_text(json.dumps(summary_json, indent=2), encoding="utf-8")
print("wrote artifacts/demo_all_summary.md")
print("wrote artifacts/demo_all_summary.json")
PY

echo "demo_proposal_flow exit code: $FLOW_EXIT_CODE"
echo "demo_checker_config exit code: $CHECKER_EXIT_CODE"
cat artifacts/demo_all_summary.md
cat artifacts/demo_all_summary.json

python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("artifacts/demo_all_summary.json").read_text(encoding="utf-8"))
if summary.get("bundle_status") != "PASS":
    raise SystemExit(1)
PY
