#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/repair_loop_safety_demo

cat > artifacts/repair_loop_safety_demo/source_pass.json <<'JSON'
{
  "proposal_id": "repair-loop-safety-source-001",
  "status": "PASS",
  "policy_decision": "PASS",
  "policy_reasons": [],
  "fail_reasons": []
}
JSON

cat > artifacts/repair_loop_safety_demo/baseline_mismatch.json <<'JSON'
{
  "schema_version": "0.1.0",
  "run_id": "baseline-safety-1",
  "backend": "openmodelica_docker",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "status": "success",
  "gate": "PASS",
  "check_ok": true,
  "simulate_ok": true,
  "metrics": {"runtime_seconds": 0.1}
}
JSON

set +e
python3 -m gateforge.repair_loop \
  --source artifacts/repair_loop_safety_demo/source_pass.json \
  --planner-backend rule \
  --baseline artifacts/repair_loop_safety_demo/baseline_mismatch.json \
  --block-new-reason-prefix strict_ \
  --out artifacts/repair_loop_safety_demo/summary.json \
  --report artifacts/repair_loop_safety_demo/summary.md
EXIT_CODE=$?
set -e

cat artifacts/repair_loop_safety_demo/summary.json
cat artifacts/repair_loop_safety_demo/summary.md

EXIT_CODE="$EXIT_CODE" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(Path("artifacts/repair_loop_safety_demo/summary.json").read_text(encoding="utf-8"))
exit_code = int(os.environ.get("EXIT_CODE", "0"))
after_reasons = payload.get("after", {}).get("reasons", []) or []
flags = {
    "expect_nonzero_exit": "PASS" if exit_code != 0 else "FAIL",
    "expect_safety_guard_triggered": "PASS" if payload.get("safety_guard_triggered") else "FAIL",
    "expect_after_fail": "PASS" if payload.get("after", {}).get("status") == "FAIL" else "FAIL",
    "expect_safety_reason_present": "PASS"
    if any(str(r).startswith("repair_safety_new_critical_reason:") for r in after_reasons)
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "exit_code": exit_code,
    "status": payload.get("status"),
    "after_status": payload.get("after", {}).get("status"),
    "safety_guard_triggered": payload.get("safety_guard_triggered"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
Path("artifacts/repair_loop_safety_demo/demo_summary.json").write_text(
    json.dumps(summary, indent=2), encoding="utf-8"
)
Path("artifacts/repair_loop_safety_demo/demo_summary.md").write_text(
    "\n".join(
        [
            "# Repair Loop Safety Guard Demo",
            "",
            f"- exit_code: `{summary['exit_code']}`",
            f"- status: `{summary['status']}`",
            f"- after_status: `{summary['after_status']}`",
            f"- safety_guard_triggered: `{summary['safety_guard_triggered']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- expect_nonzero_exit: `{flags['expect_nonzero_exit']}`",
            f"- expect_safety_guard_triggered: `{flags['expect_safety_guard_triggered']}`",
            f"- expect_after_fail: `{flags['expect_after_fail']}`",
            f"- expect_safety_reason_present: `{flags['expect_safety_reason_present']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/repair_loop_safety_demo/demo_summary.json
cat artifacts/repair_loop_safety_demo/demo_summary.md
