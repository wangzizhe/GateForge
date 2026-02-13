#!/usr/bin/env bash
set -euo pipefail

# Demo: steady_state_regression checker catches behavior drift even when compile/simulate are successful.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
POLICY_PROFILE="${POLICY_PROFILE:-}"

mkdir -p artifacts

cat > artifacts/steady_state_demo_baseline.json <<'EOF'
{
  "schema_version": "0.1.0",
  "proposal_id": "proposal-checker-steady-state-demo-0001",
  "run_id": "steady-state-demo-base-1",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "status": "success",
  "failure_type": "none",
  "gate": "PASS",
  "check_ok": true,
  "simulate_ok": true,
  "metrics": {
    "runtime_seconds": 0.5,
    "events": 8,
    "steady_state_error": 0.02
  },
  "artifacts": {
    "log_excerpt": "baseline"
  }
}
EOF

cat > artifacts/steady_state_demo_candidate.json <<'EOF'
{
  "schema_version": "0.1.0",
  "proposal_id": "proposal-checker-steady-state-demo-0001",
  "run_id": "steady-state-demo-cand-1",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "status": "success",
  "failure_type": "none",
  "gate": "PASS",
  "check_ok": true,
  "simulate_ok": true,
  "metrics": {
    "runtime_seconds": 0.5,
    "events": 8,
    "steady_state_error": 0.12
  },
  "artifacts": {
    "log_excerpt": "candidate"
  }
}
EOF

RUN_CMD=(
  python3 -m gateforge.regress
  --proposal examples/proposals/proposal_checker_steady_state_demo.json
  --candidate artifacts/steady_state_demo_candidate.json
  --baseline artifacts/steady_state_demo_baseline.json
  --runtime-threshold 10
  --out artifacts/steady_state_demo_regression.json
)
if [[ -n "$POLICY_PROFILE" ]]; then
  RUN_CMD+=(--policy "policies/profiles/${POLICY_PROFILE}.json")
fi

set +e
"${RUN_CMD[@]}"
RUN_EXIT_CODE=$?
set -e

cat artifacts/steady_state_demo_regression.json
echo "gateforge.regress exit code: $RUN_EXIT_CODE"

export GATEFORGE_RUN_EXIT_CODE="$RUN_EXIT_CODE"
python3 - <<'PY'
import json
import os
from pathlib import Path

reg_payload = json.loads(Path("artifacts/steady_state_demo_regression.json").read_text(encoding="utf-8"))

lines = [
    "# Steady-State Checker Demo Summary",
    "",
    f"- proposal_id: `{reg_payload.get('proposal_id')}`",
    f"- decision: `{reg_payload.get('decision')}`",
    f"- policy_decision: `{reg_payload.get('policy_decision')}`",
    f"- policy_path: `{reg_payload.get('policy_path')}`",
    f"- checkers: `{','.join(reg_payload.get('checkers', []))}`",
    f"- checker_config: `{json.dumps(reg_payload.get('checker_config', {}), separators=(',', ':'))}`",
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
Path("artifacts/steady_state_demo_summary.md").write_text("\n".join(lines), encoding="utf-8")
print("wrote artifacts/steady_state_demo_summary.md")
PY
