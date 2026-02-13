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

def read_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))

proposal = read_json("artifacts/proposal_run_demo.json")
checker = read_json("artifacts/checker_demo_run.json")

lines = [
    "# GateForge Demo Bundle Summary",
    "",
    f"- flow_exit_code: `{os.getenv('GATEFORGE_FLOW_EXIT_CODE', 'unknown')}`",
    f"- checker_exit_code: `{os.getenv('GATEFORGE_CHECKER_EXIT_CODE', 'unknown')}`",
    f"- proposal_flow_status: `{proposal.get('status')}`",
    f"- checker_demo_status: `{checker.get('status')}`",
    f"- checker_demo_policy_decision: `{checker.get('policy_decision')}`",
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

Path("artifacts/demo_all_summary.md").write_text("\n".join(lines), encoding="utf-8")
print("wrote artifacts/demo_all_summary.md")
PY

echo "demo_proposal_flow exit code: $FLOW_EXIT_CODE"
echo "demo_checker_config exit code: $CHECKER_EXIT_CODE"
cat artifacts/demo_all_summary.md
