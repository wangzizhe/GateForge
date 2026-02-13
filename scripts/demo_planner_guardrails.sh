#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/planner_guardrails_demo

cat > artifacts/planner_guardrails_demo/low_conf_context.json <<'JSON'
{
  "change_plan_confidence": 0.4
}
JSON

python3 -m gateforge.llm_planner \
  --goal "apply deterministic patch and run" \
  --planner-backend rule \
  --emit-change-set-draft \
  --change-plan-confidence-min 0.8 \
  --out artifacts/planner_guardrails_demo/pass_intent.json

set +e
python3 -m gateforge.llm_planner \
  --goal "apply deterministic patch and run" \
  --planner-backend rule \
  --emit-change-set-draft \
  --context-json artifacts/planner_guardrails_demo/low_conf_context.json \
  --change-plan-confidence-min 0.8 \
  --out artifacts/planner_guardrails_demo/fail_low_conf_intent.json
LOW_CODE=$?

python3 -m gateforge.llm_planner \
  --goal "apply deterministic patch and run" \
  --planner-backend rule \
  --emit-change-set-draft \
  --change-plan-allowed-file examples/openmodelica/MediumOscillator.mo \
  --out artifacts/planner_guardrails_demo/fail_whitelist_intent.json
WHITE_CODE=$?
set -e

export LOW_CODE WHITE_CODE
python3 - <<'PY'
import json
import os
from pathlib import Path

pass_payload = json.loads(Path("artifacts/planner_guardrails_demo/pass_intent.json").read_text(encoding="utf-8"))
guard = pass_payload.get("planner_inputs", {}).get("change_plan_guardrails", {})
low_code = int(os.getenv("LOW_CODE", "99"))
white_code = int(os.getenv("WHITE_CODE", "99"))

summary = {
    "pass_case": {
        "status": "PASS" if guard.get("plan_confidence_min", 0) >= 0.8 else "FAIL",
        "plan_confidence_min": guard.get("plan_confidence_min"),
    },
    "low_confidence_case": {"status": "PASS" if low_code == 1 else "FAIL", "exit_code": low_code},
    "whitelist_case": {"status": "PASS" if white_code == 1 else "FAIL", "exit_code": white_code},
}
summary["result_flags"] = {
    "pass_case_expected_pass": summary["pass_case"]["status"],
    "low_confidence_expected_fail": summary["low_confidence_case"]["status"],
    "whitelist_expected_fail": summary["whitelist_case"]["status"],
}
summary["bundle_status"] = (
    "PASS"
    if all(v == "PASS" for v in summary["result_flags"].values())
    else "FAIL"
)

Path("artifacts/planner_guardrails_demo/summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

lines = [
    "# Planner Guardrails Demo",
    "",
    f"- pass_case_status: `{summary['pass_case']['status']}`",
    f"- low_confidence_case_status: `{summary['low_confidence_case']['status']}`",
    f"- whitelist_case_status: `{summary['whitelist_case']['status']}`",
    f"- bundle_status: `{summary['bundle_status']}`",
    "",
    "## Result Flags",
    "",
    f"- pass_case_expected_pass: `{summary['result_flags']['pass_case_expected_pass']}`",
    f"- low_confidence_expected_fail: `{summary['result_flags']['low_confidence_expected_fail']}`",
    f"- whitelist_expected_fail: `{summary['result_flags']['whitelist_expected_fail']}`",
]
Path("artifacts/planner_guardrails_demo/summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"bundle_status": summary["bundle_status"]}))
PY

python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("artifacts/planner_guardrails_demo/summary.json").read_text(encoding="utf-8"))
if summary.get("bundle_status") != "PASS":
    raise SystemExit(1)
PY

cat artifacts/planner_guardrails_demo/summary.json
cat artifacts/planner_guardrails_demo/summary.md
