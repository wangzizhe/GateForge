#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/agent_invariant_guard_demo
rm -f artifacts/agent_invariant_guard_demo/*.json artifacts/agent_invariant_guard_demo/*.md

cat > artifacts/agent_invariant_guard_demo/proposal_medium.json <<'EOF'
{
  "schema_version": "0.1.0",
  "proposal_id": "proposal-invariant-medium-001",
  "timestamp_utc": "2026-02-16T10:00:00Z",
  "author_type": "agent",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "change_summary": "agent proposal with physical invariants (medium risk)",
  "requested_actions": ["check", "regress"],
  "risk_level": "medium",
  "checkers": ["invariant_guard"],
  "physical_invariants": [
    {"type": "range", "metric": "steady_state_error", "min": 0.0, "max": 0.08},
    {"type": "monotonic", "metric": "energy", "direction": "non_increasing"},
    {"type": "bounded_delta", "metric": "overshoot", "max_abs_delta": 0.1}
  ]
}
EOF

cat > artifacts/agent_invariant_guard_demo/proposal_high.json <<'EOF'
{
  "schema_version": "0.1.0",
  "proposal_id": "proposal-invariant-high-001",
  "timestamp_utc": "2026-02-16T10:00:00Z",
  "author_type": "agent",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "change_summary": "agent proposal with physical invariants (high risk)",
  "requested_actions": ["check", "regress"],
  "risk_level": "high",
  "checkers": ["invariant_guard"],
  "physical_invariants": [
    {"type": "range", "metric": "steady_state_error", "min": 0.0, "max": 0.08},
    {"type": "monotonic", "metric": "energy", "direction": "non_increasing"},
    {"type": "bounded_delta", "metric": "overshoot", "max_abs_delta": 0.1}
  ]
}
EOF

cat > artifacts/agent_invariant_guard_demo/baseline.json <<'EOF'
{
  "schema_version": "0.1.0",
  "run_id": "inv-base-1",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "status": "success",
  "gate": "PASS",
  "check_ok": true,
  "simulate_ok": true,
  "metrics": {
    "runtime_seconds": 0.5,
    "events": 10,
    "steady_state_error": 0.05,
    "energy": 1.0,
    "overshoot": 0.1
  }
}
EOF

cat > artifacts/agent_invariant_guard_demo/candidate_pass.json <<'EOF'
{
  "schema_version": "0.1.0",
  "run_id": "inv-cand-pass-1",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "status": "success",
  "gate": "PASS",
  "check_ok": true,
  "simulate_ok": true,
  "metrics": {
    "runtime_seconds": 0.52,
    "events": 11,
    "steady_state_error": 0.06,
    "energy": 0.95,
    "overshoot": 0.15
  }
}
EOF

cat > artifacts/agent_invariant_guard_demo/candidate_fail.json <<'EOF'
{
  "schema_version": "0.1.0",
  "run_id": "inv-cand-fail-1",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "status": "success",
  "gate": "PASS",
  "check_ok": true,
  "simulate_ok": true,
  "metrics": {
    "runtime_seconds": 0.54,
    "events": 11,
    "steady_state_error": 0.2,
    "energy": 1.2,
    "overshoot": 0.35
  }
}
EOF

python3 -m gateforge.regress \
  --proposal artifacts/agent_invariant_guard_demo/proposal_medium.json \
  --baseline artifacts/agent_invariant_guard_demo/baseline.json \
  --candidate artifacts/agent_invariant_guard_demo/candidate_pass.json \
  --out artifacts/agent_invariant_guard_demo/regression_pass.json

python3 -m gateforge.regress \
  --proposal artifacts/agent_invariant_guard_demo/proposal_medium.json \
  --baseline artifacts/agent_invariant_guard_demo/baseline.json \
  --candidate artifacts/agent_invariant_guard_demo/candidate_fail.json \
  --out artifacts/agent_invariant_guard_demo/regression_medium_nonpass.json

set +e
python3 -m gateforge.regress \
  --proposal artifacts/agent_invariant_guard_demo/proposal_high.json \
  --baseline artifacts/agent_invariant_guard_demo/baseline.json \
  --candidate artifacts/agent_invariant_guard_demo/candidate_fail.json \
  --out artifacts/agent_invariant_guard_demo/regression_high_fail.json
HIGH_RC=$?
set -e
if [[ "$HIGH_RC" -ne 1 ]]; then
  echo "expected high risk invariant violation flow to exit 1, got $HIGH_RC" >&2
  exit 1
fi

python3 - <<'PY'
import json
from pathlib import Path

reg_pass = json.loads(Path("artifacts/agent_invariant_guard_demo/regression_pass.json").read_text(encoding="utf-8"))
reg_mid = json.loads(Path("artifacts/agent_invariant_guard_demo/regression_medium_nonpass.json").read_text(encoding="utf-8"))
reg_high = json.loads(Path("artifacts/agent_invariant_guard_demo/regression_high_fail.json").read_text(encoding="utf-8"))

flags = {
    "pass_expected_pass": "PASS" if reg_pass.get("decision") == "PASS" else "FAIL",
    "medium_expected_needs_review": "PASS" if reg_mid.get("decision") == "NEEDS_REVIEW" else "FAIL",
    "high_expected_fail": "PASS" if reg_high.get("decision") == "FAIL" else "FAIL",
    "medium_reasons_include_invariant": "PASS"
    if any(str(r).startswith("physical_invariant_") for r in reg_mid.get("reasons", []))
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "pass_decision": reg_pass.get("decision"),
    "medium_decision": reg_mid.get("decision"),
    "high_decision": reg_high.get("decision"),
    "medium_policy_reasons": reg_mid.get("policy_reasons", []),
    "high_policy_reasons": reg_high.get("policy_reasons", []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}

Path("artifacts/agent_invariant_guard_demo/summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
Path("artifacts/agent_invariant_guard_demo/summary.md").write_text(
    "\n".join(
        [
            "# Agent Invariant Guard Demo",
            "",
            f"- pass_decision: `{summary['pass_decision']}`",
            f"- medium_decision: `{summary['medium_decision']}`",
            f"- high_decision: `{summary['high_decision']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- pass_expected_pass: `{flags['pass_expected_pass']}`",
            f"- medium_expected_needs_review: `{flags['medium_expected_needs_review']}`",
            f"- high_expected_fail: `{flags['high_expected_fail']}`",
            f"- medium_reasons_include_invariant: `{flags['medium_reasons_include_invariant']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/agent_invariant_guard_demo/summary.json
cat artifacts/agent_invariant_guard_demo/summary.md
