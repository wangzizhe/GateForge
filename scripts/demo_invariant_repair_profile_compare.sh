#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/invariant_repair_profile_compare_demo
rm -f artifacts/invariant_repair_profile_compare_demo/*.json artifacts/invariant_repair_profile_compare_demo/*.md

cat > artifacts/invariant_repair_profile_compare_demo/source_fail.json <<'JSON'
{
  "proposal_id": "invariant-profile-compare-source-001",
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

python3 -m gateforge.repair_loop \
  --source artifacts/invariant_repair_profile_compare_demo/source_fail.json \
  --planner-backend rule \
  --invariant-repair-profile default \
  --baseline baselines/mock_minimal_probe_baseline.json \
  --out artifacts/invariant_repair_profile_compare_demo/default.json

python3 -m gateforge.invariant_repair_compare \
  --source artifacts/invariant_repair_profile_compare_demo/source_fail.json \
  --profiles default industrial_strict \
  --planner-backend rule \
  --baseline baselines/mock_minimal_probe_baseline.json \
  --out-dir artifacts/invariant_repair_profile_compare_demo \
  --out artifacts/invariant_repair_profile_compare_demo/compare.json \
  --report artifacts/invariant_repair_profile_compare_demo/compare.md

python3 - <<'PY'
import json
from pathlib import Path

compare_payload = json.loads(Path("artifacts/invariant_repair_profile_compare_demo/compare.json").read_text(encoding="utf-8"))
rows = compare_payload.get("profile_results", [])
default_payload = next((x for x in rows if x.get("profile") == "default"), {})
industrial_payload = next((x for x in rows if x.get("profile") == "industrial_strict"), {})

flags = {
    "default_profile_name": "PASS" if default_payload.get("profile") == "default" else "FAIL",
    "industrial_profile_name": "PASS"
    if industrial_payload.get("profile") == "industrial_strict"
    else "FAIL",
    "strict_confidence_higher": "PASS"
    if float(industrial_payload.get("planner_change_plan_confidence_min", 0.0))
    >= float(default_payload.get("planner_change_plan_confidence_min", 0.0))
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "status": compare_payload.get("status"),
    "best_profile": compare_payload.get("best_profile"),
    "default_status": default_payload.get("status"),
    "industrial_status": industrial_payload.get("status"),
    "default_confidence_min": default_payload.get("planner_change_plan_confidence_min"),
    "industrial_confidence_min": industrial_payload.get("planner_change_plan_confidence_min"),
    "default_total_score": default_payload.get("total_score"),
    "industrial_total_score": industrial_payload.get("total_score"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
Path("artifacts/invariant_repair_profile_compare_demo/summary.json").write_text(
    json.dumps(summary, indent=2), encoding="utf-8"
)
Path("artifacts/invariant_repair_profile_compare_demo/summary.md").write_text(
    "\n".join(
        [
            "# Invariant Repair Profile Compare Demo",
            "",
            f"- status: `{summary['status']}`",
            f"- best_profile: `{summary['best_profile']}`",
            f"- default_status: `{summary['default_status']}`",
            f"- industrial_status: `{summary['industrial_status']}`",
            f"- default_total_score: `{summary['default_total_score']}`",
            f"- industrial_total_score: `{summary['industrial_total_score']}`",
            f"- default_confidence_min: `{summary['default_confidence_min']}`",
            f"- industrial_confidence_min: `{summary['industrial_confidence_min']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- default_profile_name: `{flags['default_profile_name']}`",
            f"- industrial_profile_name: `{flags['industrial_profile_name']}`",
            f"- strict_confidence_higher: `{flags['strict_confidence_higher']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/invariant_repair_profile_compare_demo/compare.json
cat artifacts/invariant_repair_profile_compare_demo/compare.md
cat artifacts/invariant_repair_profile_compare_demo/summary.json
cat artifacts/invariant_repair_profile_compare_demo/summary.md
