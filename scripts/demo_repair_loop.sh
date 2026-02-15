#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/repair_loop

cat > artifacts/repair_loop/source_fail.json <<'JSON'
{
  "proposal_id": "repair-loop-demo-source-001",
  "status": "FAIL",
  "policy_decision": "FAIL",
  "policy_reasons": [
    "runtime_regression:1.2s>1.0s"
  ],
  "fail_reasons": [
    "regression_fail"
  ]
}
JSON

python3 -m gateforge.repair_loop \
  --source artifacts/repair_loop/source_fail.json \
  --planner-backend rule \
  --baseline baselines/mock_minimal_probe_baseline.json \
  --out artifacts/repair_loop/summary.json

cat artifacts/repair_loop/summary.json
cat artifacts/repair_loop/summary.md

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/repair_loop/summary.json").read_text(encoding="utf-8"))
result_flags = {
    "after_status_expected_pass": "PASS" if payload.get("after", {}).get("status") == "PASS" else "FAIL",
    "delta_expected_improved": "PASS" if payload.get("comparison", {}).get("delta") == "improved" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in result_flags.values()) else "FAIL"
summary = {
    "before_status": payload.get("before", {}).get("status"),
    "after_status": payload.get("after", {}).get("status"),
    "delta": payload.get("comparison", {}).get("delta"),
    "safety_guard_triggered": bool(payload.get("safety_guard_triggered")),
    "result_flags": result_flags,
    "bundle_status": bundle_status,
}
Path("artifacts/repair_loop/demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
lines = [
    "# Repair Loop Demo",
    "",
    f"- before_status: `{summary['before_status']}`",
    f"- after_status: `{summary['after_status']}`",
    f"- delta: `{summary['delta']}`",
    f"- safety_guard_triggered: `{summary['safety_guard_triggered']}`",
    f"- bundle_status: `{bundle_status}`",
    "",
    "## Result Flags",
    "",
]
for k, v in result_flags.items():
    lines.append(f"- {k}: `{v}`")
Path("artifacts/repair_loop/demo_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/repair_loop/demo_summary.json
cat artifacts/repair_loop/demo_summary.md
