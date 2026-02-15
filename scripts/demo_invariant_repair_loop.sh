#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/invariant_repair_loop_demo
rm -f artifacts/invariant_repair_loop_demo/*.json artifacts/invariant_repair_loop_demo/*.md

cat > artifacts/invariant_repair_loop_demo/source_fail.json <<'JSON'
{
  "proposal_id": "invariant-repair-loop-source-001",
  "risk_level": "high",
  "status": "FAIL",
  "policy_decision": "FAIL",
  "policy_reasons": [
    "physical_invariant_range_violated:steady_state_error"
  ],
  "checker_config": {
    "invariant_guard": {
      "invariants": [
        {"type": "range", "metric": "steady_state_error", "min": 0.0, "max": 0.08}
      ]
    }
  }
}
JSON

python3 -m gateforge.invariant_repair \
  --source artifacts/invariant_repair_loop_demo/source_fail.json \
  --out artifacts/invariant_repair_loop_demo/plan.json

python3 -m gateforge.repair_loop \
  --source artifacts/invariant_repair_loop_demo/source_fail.json \
  --planner-backend rule \
  --baseline baselines/mock_minimal_probe_baseline.json \
  --out artifacts/invariant_repair_loop_demo/summary.json

cat artifacts/invariant_repair_loop_demo/plan.json
cat artifacts/invariant_repair_loop_demo/summary.json
cat artifacts/invariant_repair_loop_demo/summary.md

python3 - <<'PY'
import json
from pathlib import Path

plan = json.loads(Path("artifacts/invariant_repair_loop_demo/plan.json").read_text(encoding="utf-8"))
summary = json.loads(Path("artifacts/invariant_repair_loop_demo/summary.json").read_text(encoding="utf-8"))

flags = {
    "plan_detected_invariant": "PASS" if plan.get("invariant_repair_detected") else "FAIL",
    "loop_applied_invariant_repair": "PASS" if summary.get("invariant_repair_applied") else "FAIL",
    "loop_after_status_expected_non_fail": "PASS"
    if summary.get("after", {}).get("status") in {"PASS", "NEEDS_REVIEW"}
    else "FAIL",
    "comparison_expected_improved": "PASS"
    if summary.get("comparison", {}).get("delta") == "improved"
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
out = {
    "plan_detected": plan.get("invariant_repair_detected"),
    "loop_applied": summary.get("invariant_repair_applied"),
    "before_status": summary.get("before", {}).get("status"),
    "after_status": summary.get("after", {}).get("status"),
    "invariant_reasons": summary.get("invariant_reasons", []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
Path("artifacts/invariant_repair_loop_demo/demo_summary.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8"
)
Path("artifacts/invariant_repair_loop_demo/demo_summary.md").write_text(
    "\n".join(
        [
            "# Invariant Repair Loop Demo",
            "",
            f"- plan_detected: `{out['plan_detected']}`",
            f"- loop_applied: `{out['loop_applied']}`",
            f"- before_status: `{out['before_status']}`",
            f"- after_status: `{out['after_status']}`",
            f"- bundle_status: `{out['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- plan_detected_invariant: `{flags['plan_detected_invariant']}`",
            f"- loop_applied_invariant_repair: `{flags['loop_applied_invariant_repair']}`",
            f"- loop_after_status_expected_non_fail: `{flags['loop_after_status_expected_non_fail']}`",
            f"- comparison_expected_improved: `{flags['comparison_expected_improved']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/invariant_repair_loop_demo/demo_summary.json
cat artifacts/invariant_repair_loop_demo/demo_summary.md
