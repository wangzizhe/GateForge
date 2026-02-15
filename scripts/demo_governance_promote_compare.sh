#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_promote_compare_demo

bash scripts/demo_governance_snapshot_from_orchestrate_compare.sh

python3 -m gateforge.governance_promote_compare \
  --snapshot artifacts/governance_snapshot_orchestrate_demo/summary.json \
  --profiles default industrial_strict \
  --min-top-score-margin 1 \
  --out-dir artifacts/governance_promote_compare_demo \
  --out artifacts/governance_promote_compare_demo/summary.json \
  --report artifacts/governance_promote_compare_demo/summary.md

cat > artifacts/governance_promote_compare_demo/override_allow_industrial.json <<'JSON'
{
  "allow_promote": true,
  "reason": "demo compare override for industrial profile",
  "approved_by": "review.committee",
  "expires_utc": "2099-01-01T00:00:00Z"
}
JSON

cat > artifacts/governance_promote_compare_demo/override_map.json <<'JSON'
{
  "industrial_strict": "artifacts/governance_promote_compare_demo/override_allow_industrial.json"
}
JSON

python3 -m gateforge.governance_promote_compare \
  --snapshot artifacts/governance_snapshot_orchestrate_demo/summary.json \
  --profiles default industrial_strict \
  --min-top-score-margin 1 \
  --override-map artifacts/governance_promote_compare_demo/override_map.json \
  --out-dir artifacts/governance_promote_compare_demo/with_override \
  --out artifacts/governance_promote_compare_demo/summary_with_override.json \
  --report artifacts/governance_promote_compare_demo/summary_with_override.md

cat artifacts/governance_promote_compare_demo/summary.json
cat artifacts/governance_promote_compare_demo/summary.md
cat artifacts/governance_promote_compare_demo/summary_with_override.json

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/governance_promote_compare_demo/summary.json").read_text(encoding="utf-8"))
payload_override = json.loads(
    Path("artifacts/governance_promote_compare_demo/summary_with_override.json").read_text(encoding="utf-8")
)
flags = {
    "expect_profiles_2": "PASS" if len(payload.get("profile_results", [])) == 2 else "FAIL",
    "expect_best_profile_present": "PASS" if isinstance(payload.get("best_profile"), str) and payload.get("best_profile") else "FAIL",
    "expect_recommended_present": "PASS"
    if isinstance(payload.get("recommended_profile"), str) and payload.get("recommended_profile")
    else "FAIL",
    "expect_override_compare_present": "PASS"
    if len(payload_override.get("profile_results", [])) == 2
    else "FAIL",
    "expect_score_margin_present": "PASS"
    if isinstance(payload.get("top_score_margin"), int)
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "status": payload.get("status"),
    "best_profile": payload.get("best_profile"),
    "best_decision": payload.get("best_decision"),
    "best_total_score": payload.get("best_total_score"),
    "best_reason": payload.get("best_reason"),
    "best_score_breakdown": payload.get("best_score_breakdown"),
    "top_score_margin": payload.get("top_score_margin"),
    "min_top_score_margin": payload.get("min_top_score_margin"),
    "recommended_profile": payload.get("recommended_profile"),
    "override_best_profile": payload_override.get("best_profile"),
    "override_best_decision": payload_override.get("best_decision"),
    "ranking_top_2": payload.get("ranking", [])[:2],
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
            f"- best_total_score: `{summary['best_total_score']}`",
            f"- best_reason: `{summary['best_reason']}`",
            f"- top_score_margin: `{summary['top_score_margin']}`",
            f"- min_top_score_margin: `{summary['min_top_score_margin']}`",
            f"- recommended_profile: `{summary['recommended_profile']}`",
            f"- override_best_profile: `{summary['override_best_profile']}`",
            f"- override_best_decision: `{summary['override_best_decision']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Best Score Breakdown",
            "",
            f"- decision_component: `{(summary.get('best_score_breakdown') or {}).get('decision_component')}`",
            f"- exit_component: `{(summary.get('best_score_breakdown') or {}).get('exit_component')}`",
            f"- reasons_component: `{(summary.get('best_score_breakdown') or {}).get('reasons_component')}`",
            f"- recommended_component: `{(summary.get('best_score_breakdown') or {}).get('recommended_component')}`",
            "",
            "## Result Flags",
            "",
            f"- expect_profiles_2: `{flags['expect_profiles_2']}`",
            f"- expect_best_profile_present: `{flags['expect_best_profile_present']}`",
            f"- expect_recommended_present: `{flags['expect_recommended_present']}`",
            f"- expect_override_compare_present: `{flags['expect_override_compare_present']}`",
            f"- expect_score_margin_present: `{flags['expect_score_margin_present']}`",
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
