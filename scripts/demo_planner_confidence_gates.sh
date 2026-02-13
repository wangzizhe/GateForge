#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
POLICY_PROFILE="${POLICY_PROFILE:-}"

mkdir -p artifacts/planner_confidence_demo

HIGH_CTX="artifacts/planner_confidence_demo/high_context.json"
MID_CTX="artifacts/planner_confidence_demo/mid_context.json"
LOW_CTX="artifacts/planner_confidence_demo/low_context.json"

cat > "$HIGH_CTX" <<'EOF'
{
  "risk_level": "low",
  "change_summary": "Planner confidence high -> should PASS",
  "change_plan_confidence": 0.9
}
EOF

cat > "$MID_CTX" <<'EOF'
{
  "risk_level": "low",
  "change_summary": "Planner confidence medium -> should NEEDS_REVIEW",
  "change_plan_confidence": 0.5
}
EOF

cat > "$LOW_CTX" <<'EOF'
{
  "risk_level": "low",
  "change_summary": "Planner confidence very low -> should FAIL",
  "change_plan_confidence": 0.2
}
EOF

run_case() {
  local case_name="$1"
  local ctx="$2"
  local expected_exit="$3"
  local out_json="artifacts/planner_confidence_demo/${case_name}.json"

  local cmd=(
    python3 -m gateforge.autopilot
    --goal "apply deterministic patch and run"
    --planner-backend rule
    --materialize-change-set
    --context-json "$ctx"
    --proposal-id "planner-confidence-${case_name}"
    --baseline baselines/mock_minimal_probe_baseline.json
    --save-run-under autopilot
    --out "$out_json"
  )
  if [[ -n "$POLICY_PROFILE" ]]; then
    cmd+=(--policy-profile "$POLICY_PROFILE")
  fi
  set +e
  "${cmd[@]}"
  local rc=$?
  set -e
  if [[ "$rc" -ne "$expected_exit" ]]; then
    echo "unexpected exit code for ${case_name}: got ${rc}, expected ${expected_exit}" >&2
    return 1
  fi
}

run_case "high" "$HIGH_CTX" 0
run_case "mid" "$MID_CTX" 0
run_case "low" "$LOW_CTX" 1

python3 - <<'PY'
import json
from pathlib import Path

high = json.loads(Path("artifacts/planner_confidence_demo/high.json").read_text(encoding="utf-8"))
mid = json.loads(Path("artifacts/planner_confidence_demo/mid.json").read_text(encoding="utf-8"))
low = json.loads(Path("artifacts/planner_confidence_demo/low.json").read_text(encoding="utf-8"))

summary = {
    "policy_profile": high.get("policy_profile") or "default",
    "high_confidence": {
        "status": high.get("status"),
        "confidence_min": high.get("change_plan_confidence_min"),
    },
    "mid_confidence": {
        "status": mid.get("status"),
        "confidence_min": mid.get("change_plan_confidence_min"),
    },
    "low_confidence": {
        "status": low.get("status"),
        "confidence_min": low.get("change_plan_confidence_min"),
    },
}
summary["result_flags"] = {
    "high_expected_pass": "PASS" if summary["high_confidence"]["status"] == "PASS" else "FAIL",
    "mid_expected_needs_review": "PASS" if summary["mid_confidence"]["status"] == "NEEDS_REVIEW" else "FAIL",
    "low_expected_nonpass": "PASS" if summary["low_confidence"]["status"] in {"FAIL", "UNKNOWN"} else "FAIL",
}
summary["bundle_status"] = "PASS" if all(v == "PASS" for v in summary["result_flags"].values()) else "FAIL"

Path("artifacts/planner_confidence_demo/summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
lines = [
    "# Planner Confidence Gates Demo",
    "",
    f"- policy_profile: `{summary['policy_profile']}`",
    f"- high_confidence_status: `{summary['high_confidence']['status']}`",
    f"- mid_confidence_status: `{summary['mid_confidence']['status']}`",
    f"- low_confidence_status: `{summary['low_confidence']['status']}`",
    f"- bundle_status: `{summary['bundle_status']}`",
    "",
    "## Result Flags",
    "",
    f"- high_expected_pass: `{summary['result_flags']['high_expected_pass']}`",
    f"- mid_expected_needs_review: `{summary['result_flags']['mid_expected_needs_review']}`",
    f"- low_expected_nonpass: `{summary['result_flags']['low_expected_nonpass']}`",
]
Path("artifacts/planner_confidence_demo/summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"bundle_status": summary["bundle_status"]}))
PY

cat artifacts/planner_confidence_demo/summary.json
cat artifacts/planner_confidence_demo/summary.md

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/planner_confidence_demo/summary.json").read_text(encoding="utf-8"))
if payload.get("bundle_status") != "PASS":
    raise SystemExit(1)
PY
