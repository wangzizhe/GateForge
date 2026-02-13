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
