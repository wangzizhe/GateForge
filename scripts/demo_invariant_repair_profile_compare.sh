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

set +e
python3 -m gateforge.repair_loop \
  --source artifacts/invariant_repair_profile_compare_demo/source_fail.json \
  --planner-backend rule \
  --invariant-repair-profile industrial_strict \
  --baseline baselines/mock_minimal_probe_baseline.json \
  --out artifacts/invariant_repair_profile_compare_demo/industrial.json
IND_RC=$?
set -e

python3 - <<'PY'
import json
from pathlib import Path

default_payload = json.loads(Path("artifacts/invariant_repair_profile_compare_demo/default.json").read_text(encoding="utf-8"))
industrial_payload = json.loads(Path("artifacts/invariant_repair_profile_compare_demo/industrial.json").read_text(encoding="utf-8"))

def score(status: str) -> int:
    if status == "PASS":
        return 2
    if status == "NEEDS_REVIEW":
        return 1
    if status == "FAIL":
        return 0
    return -1

default_status = str(default_payload.get("status"))
industrial_status = str(industrial_payload.get("status"))
relation = "unchanged"
if score(industrial_status) > score(default_status):
    relation = "upgraded"
elif score(industrial_status) < score(default_status):
    relation = "downgraded"

flags = {
    "default_profile_name": "PASS" if default_payload.get("invariant_repair_profile") == "default" else "FAIL",
    "industrial_profile_name": "PASS"
    if industrial_payload.get("invariant_repair_profile") == "industrial_strict"
    else "FAIL",
    "strict_confidence_higher": "PASS"
    if float(industrial_payload.get("planner_change_plan_confidence_min", 0.0))
    >= float(default_payload.get("planner_change_plan_confidence_min", 0.0))
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "default_status": default_status,
    "industrial_status": industrial_status,
    "relation": relation,
    "default_confidence_min": default_payload.get("planner_change_plan_confidence_min"),
    "industrial_confidence_min": industrial_payload.get("planner_change_plan_confidence_min"),
    "default_profile_version": default_payload.get("invariant_repair_profile_version"),
    "industrial_profile_version": industrial_payload.get("invariant_repair_profile_version"),
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
            f"- default_status: `{summary['default_status']}`",
            f"- industrial_status: `{summary['industrial_status']}`",
            f"- relation: `{summary['relation']}`",
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

echo "industrial_exit_code=$IND_RC"
cat artifacts/invariant_repair_profile_compare_demo/summary.json
cat artifacts/invariant_repair_profile_compare_demo/summary.md
