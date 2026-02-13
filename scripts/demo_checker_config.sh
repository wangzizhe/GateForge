#!/usr/bin/env bash
set -euo pipefail

# Demo: checker_config thresholds can trigger FAIL even when runtime-threshold is relaxed.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts

cat > artifacts/checker_demo_baseline.json <<'EOF'
{
  "schema_version": "0.1.0",
  "proposal_id": "proposal-checker-config-demo-0001",
  "run_id": "checker-demo-base-1",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "status": "success",
  "failure_type": "none",
  "gate": "PASS",
  "check_ok": true,
  "simulate_ok": true,
  "metrics": {
    "runtime_seconds": 1.0,
    "events": 10
  },
  "artifacts": {
    "log_excerpt": "baseline"
  }
}
EOF

cat > artifacts/checker_demo_candidate.json <<'EOF'
{
  "schema_version": "0.1.0",
  "proposal_id": "proposal-checker-config-demo-0001",
  "run_id": "checker-demo-cand-1",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "status": "success",
  "failure_type": "none",
  "gate": "PASS",
  "check_ok": true,
  "simulate_ok": true,
  "metrics": {
    "runtime_seconds": 1.6,
    "events": 16
  },
  "artifacts": {
    "log_excerpt": "candidate"
  }
}
EOF

set +e
python3 -m gateforge.run \
  --proposal examples/proposals/proposal_checker_config_demo.json \
  --candidate-in artifacts/checker_demo_candidate.json \
  --baseline artifacts/checker_demo_baseline.json \
  --runtime-threshold 10 \
  --regression-out artifacts/checker_demo_regression.json \
  --out artifacts/checker_demo_run.json
RUN_EXIT_CODE=$?
set -e

cat artifacts/checker_demo_run.json
cat artifacts/checker_demo_regression.json
echo "gateforge.run exit code: $RUN_EXIT_CODE"

export GATEFORGE_RUN_EXIT_CODE="$RUN_EXIT_CODE"
python3 - <<'PY'
import json
import os
from pathlib import Path

run_payload = json.loads(Path("artifacts/checker_demo_run.json").read_text(encoding="utf-8"))
reg_payload = json.loads(Path("artifacts/checker_demo_regression.json").read_text(encoding="utf-8"))

lines = [
    "# Checker Config Demo Summary",
    "",
    f"- proposal_id: `{run_payload.get('proposal_id')}`",
    f"- status: `{run_payload.get('status')}`",
    f"- policy_decision: `{run_payload.get('policy_decision')}`",
    f"- checkers: `{','.join(run_payload.get('checkers', []))}`",
    f"- checker_config: `{json.dumps(run_payload.get('checker_config', {}), separators=(',', ':'))}`",
    f"- run_exit_code: `{os.getenv('GATEFORGE_RUN_EXIT_CODE', 'unknown')}`",
    "",
    "## Reasons",
    "",
]
reasons = reg_payload.get("reasons", [])
if reasons:
    lines.extend([f"- `{r}`" for r in reasons])
else:
    lines.append("- `none`")

lines.extend(["", "## Checker Findings", ""])
findings = reg_payload.get("findings", [])
if findings:
    for finding in findings:
        lines.append(
            f"- `{finding.get('checker')}` `{finding.get('reason')}`: {finding.get('message')}"
        )
else:
    lines.append("- `none`")

lines.append("")
Path("artifacts/checker_demo_summary.md").write_text("\n".join(lines), encoding="utf-8")
print("wrote artifacts/checker_demo_summary.md")
PY
