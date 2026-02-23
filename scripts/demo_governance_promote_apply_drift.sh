#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_promote_apply_drift_demo
rm -f artifacts/governance_promote_apply_drift_demo/*.json artifacts/governance_promote_apply_drift_demo/*.md artifacts/governance_promote_apply_drift_demo/*.jsonl

python3 - <<'PY'
import json
from pathlib import Path

compare_summary = {
    "status": "PASS",
    "best_profile": "default",
    "best_decision": "PASS",
    "recommended_profile": "default",
    "best_reason": "highest_total_score",
    "best_total_score": 203,
    "top_score_margin": 4,
    "min_top_score_margin": 1,
    "decision_explanations": {
        "selection_priority": [
            "total_score",
            "decision",
            "exit_code",
            "recommended_profile_tiebreak",
        ],
        "best_vs_others": [
            {
                "winner_profile": "default",
                "challenger_profile": "industrial_strict",
                "winner_total_score": 203,
                "challenger_total_score": 199,
                "score_margin": 4,
                "tie_on_total_score": False,
                "winner_advantages": ["recommended_component"],
            }
        ],
    },
    "explanation_quality": {
        "score": 100,
        "checks": {
            "has_selection_priority": True,
            "has_pairwise_rows": True,
            "all_pairwise_have_margin": True,
            "all_pairwise_have_profiles": True,
            "pairwise_advantages_non_empty": True,
        },
    },
}
Path("artifacts/governance_promote_apply_drift_demo/synthetic_pass_compare.json").write_text(
    json.dumps(compare_summary, indent=2),
    encoding="utf-8",
)
PY

python3 -m gateforge.governance_promote_apply \
  --compare-summary artifacts/governance_promote_apply_drift_demo/synthetic_pass_compare.json \
  --policy-profile default \
  --out artifacts/governance_promote_apply_drift_demo/baseline_apply.json \
  --report artifacts/governance_promote_apply_drift_demo/baseline_apply.md \
  --audit artifacts/governance_promote_apply_drift_demo/decision_audit.jsonl

python3 -m gateforge.governance_promote_apply \
  --compare-summary artifacts/governance_promote_apply_drift_demo/synthetic_pass_compare.json \
  --policy-profile industrial_strict \
  --baseline-apply-summary artifacts/governance_promote_apply_drift_demo/baseline_apply.json \
  --out artifacts/governance_promote_apply_drift_demo/drift_needs_review.json \
  --report artifacts/governance_promote_apply_drift_demo/drift_needs_review.md \
  --audit artifacts/governance_promote_apply_drift_demo/decision_audit.jsonl

set +e
python3 -m gateforge.governance_promote_apply \
  --compare-summary artifacts/governance_promote_apply_drift_demo/synthetic_pass_compare.json \
  --policy-profile industrial_strict \
  --baseline-apply-summary artifacts/governance_promote_apply_drift_demo/baseline_apply.json \
  --strict-guardrail-drift \
  --out artifacts/governance_promote_apply_drift_demo/drift_strict_fail.json \
  --report artifacts/governance_promote_apply_drift_demo/drift_strict_fail.md \
  --audit artifacts/governance_promote_apply_drift_demo/decision_audit.jsonl
STRICT_RC=$?
set -e

python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/governance_promote_apply_drift_demo")
baseline = json.loads((root / "baseline_apply.json").read_text(encoding="utf-8"))
drift_review = json.loads((root / "drift_needs_review.json").read_text(encoding="utf-8"))
drift_fail = json.loads((root / "drift_strict_fail.json").read_text(encoding="utf-8"))

flags = {
    "baseline_expected_pass": "PASS" if baseline.get("final_status") == "PASS" else "FAIL",
    "drift_expected_needs_review": "PASS"
    if drift_review.get("final_status") == "NEEDS_REVIEW"
    and drift_review.get("guardrail_drift_detected") is True
    else "FAIL",
    "strict_drift_expected_fail": "PASS"
    if drift_fail.get("final_status") == "FAIL"
    and drift_fail.get("strict_guardrail_drift") is True
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "baseline_policy_hash": baseline.get("policy_hash"),
    "baseline_effective_guardrails_hash": baseline.get("effective_guardrails_hash"),
    "drift_needs_review_status": drift_review.get("final_status"),
    "drift_needs_review_reasons": drift_review.get("reasons", []),
    "drift_strict_fail_status": drift_fail.get("final_status"),
    "drift_strict_fail_reasons": drift_fail.get("reasons", []),
    "drift_detected": bool(drift_review.get("guardrail_drift_detected")),
    "result_flags": flags,
    "bundle_status": bundle_status,
}

(root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(root / "summary.md").write_text(
    "\n".join(
        [
            "# Governance Promote Apply Drift Demo",
            "",
            f"- drift_needs_review_status: `{summary['drift_needs_review_status']}`",
            f"- drift_strict_fail_status: `{summary['drift_strict_fail_status']}`",
            f"- drift_detected: `{summary['drift_detected']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- baseline_expected_pass: `{flags['baseline_expected_pass']}`",
            f"- drift_expected_needs_review: `{flags['drift_expected_needs_review']}`",
            f"- strict_drift_expected_fail: `{flags['strict_drift_expected_fail']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

if [[ "$STRICT_RC" -ne 1 ]]; then
  echo "expected strict guardrail drift flow to exit 1, got $STRICT_RC" >&2
  exit 1
fi

cat artifacts/governance_promote_apply_drift_demo/summary.json
cat artifacts/governance_promote_apply_drift_demo/summary.md
