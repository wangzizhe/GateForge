#!/usr/bin/env bash
set -euo pipefail

mkdir -p artifacts/behavior_metrics_demo

cat > artifacts/behavior_metrics_demo/baseline.json <<'JSON'
{
  "schema_version": "0.1.0",
  "proposal_id": "proposal-behavior-metrics-demo-0001",
  "run_id": "behavior-base-1",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "status": "success",
  "failure_type": "none",
  "gate": "PASS",
  "check_ok": true,
  "simulate_ok": true,
  "metrics": {
    "runtime_seconds": 1.0,
    "events": 10,
    "overshoot": 0.1,
    "settling_time": 1.0,
    "steady_state_error": 0.02
  },
  "artifacts": {
    "log_excerpt": "baseline"
  }
}
JSON

cat > artifacts/behavior_metrics_demo/candidate.json <<'JSON'
{
  "schema_version": "0.1.0",
  "proposal_id": "proposal-behavior-metrics-demo-0001",
  "run_id": "behavior-cand-1",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "status": "success",
  "failure_type": "none",
  "gate": "PASS",
  "check_ok": true,
  "simulate_ok": true,
  "metrics": {
    "runtime_seconds": 1.0,
    "events": 10,
    "overshoot": 0.3,
    "settling_time": 2.0,
    "steady_state_error": 0.12
  },
  "artifacts": {
    "log_excerpt": "candidate"
  }
}
JSON

cat > artifacts/behavior_metrics_demo/proposal.json <<'JSON'
{
  "schema_version": "0.1.0",
  "proposal_id": "proposal-behavior-metrics-demo-0001",
  "timestamp_utc": "2026-02-13T00:00:00Z",
  "author_type": "human",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "change_summary": "behavior metrics checker demo",
  "requested_actions": ["check", "regress"],
  "risk_level": "medium",
  "checkers": ["control_behavior_regression"],
  "checker_config": {
    "control_behavior_regression": {
      "max_overshoot_abs_delta": 0.1,
      "max_settling_time_ratio": 1.5,
      "max_steady_state_abs_delta": 0.05
    }
  }
}
JSON

set +e
python3 -m gateforge.regress \
  --proposal artifacts/behavior_metrics_demo/proposal.json \
  --candidate artifacts/behavior_metrics_demo/candidate.json \
  --baseline artifacts/behavior_metrics_demo/baseline.json \
  --out artifacts/behavior_metrics_demo/regression.json
EXIT_CODE=$?
set -e

cat artifacts/behavior_metrics_demo/regression.json

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/behavior_metrics_demo/regression.json").read_text(encoding="utf-8"))
reasons = payload.get("reasons", [])

flags = {
    "decision_expected_needs_review": "PASS" if payload.get("decision") == "NEEDS_REVIEW" else "FAIL",
    "overshoot_reason_present": "PASS" if "overshoot_regression_detected" in reasons else "FAIL",
    "settling_reason_present": "PASS" if "settling_time_regression_detected" in reasons else "FAIL",
    "steady_reason_present": "PASS" if "steady_state_regression_detected" in reasons else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "decision": payload.get("decision"),
    "reasons": reasons,
    "result_flags": flags,
    "bundle_status": bundle_status,
}
Path("artifacts/behavior_metrics_demo/summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

lines = [
    "# Behavior Metrics Checker Demo",
    "",
    f"- decision: `{summary['decision']}`",
    f"- bundle_status: `{bundle_status}`",
    "",
    "## Reasons",
    "",
]
if reasons:
    lines.extend([f"- `{r}`" for r in reasons])
else:
    lines.append("- `none`")
lines.extend(["", "## Result Flags", ""])
for key, value in flags.items():
    lines.append(f"- {key}: `{value}`")
Path("artifacts/behavior_metrics_demo/summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

print(json.dumps({"bundle_status": bundle_status}))
PY

cat artifacts/behavior_metrics_demo/summary.json
cat artifacts/behavior_metrics_demo/summary.md

if [[ "$EXIT_CODE" -ne 0 ]]; then
  echo "Unexpected non-zero exit code: $EXIT_CODE"
  exit 1
fi

python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("artifacts/behavior_metrics_demo/summary.json").read_text(encoding="utf-8"))
if payload.get("bundle_status") != "PASS":
    raise SystemExit(1)
PY
