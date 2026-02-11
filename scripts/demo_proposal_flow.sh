#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROPOSAL_PATH="examples/proposals/proposal_demo_mock.json"
RUN_OUT="artifacts/proposal_run_demo.json"
CANDIDATE_OUT="artifacts/candidate_from_proposal_demo.json"
REGRESSION_OUT="artifacts/regression_from_proposal_demo.json"
DEMO_BASELINE="artifacts/baseline_demo_mock.json"

python3 -m gateforge.proposal_validate --in "$PROPOSAL_PATH"

# Build a demo baseline aligned with proposal backend/model_script.
python3 - <<'PY'
import json
from pathlib import Path

proposal = json.loads(Path("examples/proposals/proposal_demo_mock.json").read_text(encoding="utf-8"))
baseline = json.loads(Path("baselines/mock_baseline.json").read_text(encoding="utf-8"))
baseline["model_script"] = proposal["model_script"]
Path("artifacts/baseline_demo_mock.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")
PY

python3 -m gateforge.run \
  --proposal "$PROPOSAL_PATH" \
  --baseline "$DEMO_BASELINE" \
  --candidate-out "$CANDIDATE_OUT" \
  --regression-out "$REGRESSION_OUT" \
  --out "$RUN_OUT"

python3 - <<'PY'
import json
from pathlib import Path

run = json.loads(Path("artifacts/proposal_run_demo.json").read_text(encoding="utf-8"))
reg = json.loads(Path("artifacts/regression_from_proposal_demo.json").read_text(encoding="utf-8"))

print("\n[GateForge Demo Summary]")
print(f"proposal_id      : {run.get('proposal_id')}")
print(f"run status       : {run.get('status')}")
print(f"policy decision  : {run.get('policy_decision')}")
print(f"candidate path   : {run.get('candidate_path')}")
print(f"baseline path    : {run.get('baseline_path')}")
print(f"regression path  : {run.get('regression_path')}")
print(f"regression reason: {reg.get('reasons')}")
print(f"policy reasons   : {reg.get('policy_reasons')}")
PY
