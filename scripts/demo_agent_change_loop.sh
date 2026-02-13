#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
POLICY_PROFILE="${POLICY_PROFILE:-}"

mkdir -p artifacts/agent_change_loop

LOW_OUT="artifacts/agent_change_loop/low_summary.json"
HIGH_OUT="artifacts/agent_change_loop/high_summary.json"

LOW_CMD=(
  python3 -m gateforge.autopilot
  --goal "apply deterministic patch and run"
  --planner-backend rule
  --materialize-change-set
  --proposal-id agent-change-loop-low-001
  --baseline baselines/mock_minimal_probe_baseline.json
  --save-run-under autopilot
  --out "$LOW_OUT"
)
if [[ -n "$POLICY_PROFILE" ]]; then
  LOW_CMD+=(--policy-profile "$POLICY_PROFILE")
fi
"${LOW_CMD[@]}"

cat > artifacts/agent_change_loop/high_context.json <<'EOF'
{
  "risk_level": "high",
  "change_summary": "High-risk change requires manual approval before auto-apply"
}
EOF

HIGH_CMD=(
  python3 -m gateforge.autopilot
  --goal "apply deterministic patch and run"
  --planner-backend rule
  --materialize-change-set
  --proposal-id agent-change-loop-high-001
  --context-json artifacts/agent_change_loop/high_context.json
  --baseline baselines/mock_minimal_probe_baseline.json
  --save-run-under autopilot
  --out "$HIGH_OUT"
)
if [[ -n "$POLICY_PROFILE" ]]; then
  HIGH_CMD+=(--policy-profile "$POLICY_PROFILE")
fi
"${HIGH_CMD[@]}"

python3 - <<'PY'
import json
from pathlib import Path

low = json.loads(Path("artifacts/agent_change_loop/low_summary.json").read_text(encoding="utf-8"))
high = json.loads(Path("artifacts/agent_change_loop/high_summary.json").read_text(encoding="utf-8"))

summary = {
    "policy_profile": high.get("policy_profile") or low.get("policy_profile") or "default",
    "low_risk_status": low.get("status"),
    "high_risk_status": high.get("status"),
    "low_risk_change_apply_status": low.get("change_apply_status"),
    "high_risk_change_apply_status": high.get("change_apply_status"),
    "high_risk_required_human_checks_count": len(high.get("required_human_checks", [])),
}
summary["result_flags"] = {
    "low_risk_expected_pass": "PASS" if summary["low_risk_status"] == "PASS" else "FAIL",
    "high_risk_expected_needs_review": "PASS" if summary["high_risk_status"] == "NEEDS_REVIEW" else "FAIL",
}
summary["bundle_status"] = (
    "PASS"
    if all(v == "PASS" for v in summary["result_flags"].values())
    else "FAIL"
)

Path("artifacts/agent_change_loop/summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
lines = [
    "# Agent Change Safety Loop Demo",
    "",
    f"- policy_profile: `{summary['policy_profile']}`",
    f"- low_risk_status: `{summary['low_risk_status']}`",
    f"- high_risk_status: `{summary['high_risk_status']}`",
    f"- low_risk_change_apply_status: `{summary['low_risk_change_apply_status']}`",
    f"- high_risk_change_apply_status: `{summary['high_risk_change_apply_status']}`",
    f"- high_risk_required_human_checks_count: `{summary['high_risk_required_human_checks_count']}`",
    f"- bundle_status: `{summary['bundle_status']}`",
    "",
    "## Result Flags",
    "",
    f"- low_risk_expected_pass: `{summary['result_flags']['low_risk_expected_pass']}`",
    f"- high_risk_expected_needs_review: `{summary['result_flags']['high_risk_expected_needs_review']}`",
]
Path("artifacts/agent_change_loop/summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"bundle_status": summary["bundle_status"]}))
PY

cat artifacts/agent_change_loop/summary.json
cat artifacts/agent_change_loop/summary.md

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/agent_change_loop/summary.json").read_text(encoding="utf-8"))
if payload.get("bundle_status") != "PASS":
    raise SystemExit(1)
PY

