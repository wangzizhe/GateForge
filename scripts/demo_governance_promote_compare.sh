#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_promote_compare_demo

bash scripts/demo_governance_snapshot_from_orchestrate_compare.sh

python3 -m gateforge.governance_promote_compare \
  --snapshot artifacts/governance_snapshot_orchestrate_demo/summary.json \
  --profiles default industrial_strict \
  --out-dir artifacts/governance_promote_compare_demo \
  --out artifacts/governance_promote_compare_demo/summary.json \
  --report artifacts/governance_promote_compare_demo/summary.md

cat artifacts/governance_promote_compare_demo/summary.json
cat artifacts/governance_promote_compare_demo/summary.md

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/governance_promote_compare_demo/summary.json").read_text(encoding="utf-8"))
flags = {
    "expect_profiles_2": "PASS" if len(payload.get("profile_results", [])) == 2 else "FAIL",
    "expect_best_profile_present": "PASS" if isinstance(payload.get("best_profile"), str) and payload.get("best_profile") else "FAIL",
    "expect_recommended_present": "PASS"
    if isinstance(payload.get("recommended_profile"), str) and payload.get("recommended_profile")
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "status": payload.get("status"),
    "best_profile": payload.get("best_profile"),
    "best_decision": payload.get("best_decision"),
    "recommended_profile": payload.get("recommended_profile"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
Path("artifacts/governance_promote_compare_demo/demo_summary.json").write_text(
    json.dumps(summary, indent=2), encoding="utf-8"
)
Path("artifacts/governance_promote_compare_demo/demo_summary.md").write_text(
    "\n".join(
        [
            "# Governance Promote Compare Demo",
            "",
            f"- status: `{summary['status']}`",
            f"- best_profile: `{summary['best_profile']}`",
            f"- best_decision: `{summary['best_decision']}`",
            f"- recommended_profile: `{summary['recommended_profile']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- expect_profiles_2: `{flags['expect_profiles_2']}`",
            f"- expect_best_profile_present: `{flags['expect_best_profile_present']}`",
            f"- expect_recommended_present: `{flags['expect_recommended_present']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/governance_promote_compare_demo/demo_summary.json
cat artifacts/governance_promote_compare_demo/demo_summary.md
