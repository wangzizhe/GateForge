#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_promote_apply_explanation_structure_demo
rm -f artifacts/governance_promote_apply_explanation_structure_demo/*.json artifacts/governance_promote_apply_explanation_structure_demo/*.md artifacts/governance_promote_apply_explanation_structure_demo/*.jsonl

python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/governance_promote_apply_explanation_structure_demo")
base = {
    "status": "PASS",
    "best_profile": "default",
    "best_decision": "PASS",
    "recommended_profile": "default",
    "top_score_margin": 4,
    "explanation_quality": {"score": 100},
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
                "score_margin": 4,
                "tie_on_total_score": False,
                "winner_advantages": ["recommended_component"],
            }
        ],
    },
}
complete = {
    **base,
    "decision_explanation_ranked": [
        {
            "reason": "top_score_margin",
            "value": 4,
            "weight": 100,
            "note": "Best profile leads second-best by score margin.",
        },
        {
            "reason": "component_delta:decision_component",
            "value": 100,
            "weight": 90,
            "note": "Decision component drives most of the margin.",
        },
        {
            "reason": "best_reason",
            "value": "highest_total_score",
            "weight": 40,
            "note": "Primary selection rule.",
        },
    ],
    "explanation_completeness": 100,
    "decision_explanation_ranking_details": {
        "top_driver": "component_delta:decision_component",
        "numeric_reason_count": 2,
        "drivers": [
            {
                "rank": 1,
                "reason": "component_delta:decision_component",
                "weight": 90,
                "value": 100,
                "impact_score": 9000,
                "impact_share_pct": 95.64,
            },
            {
                "rank": 2,
                "reason": "top_score_margin",
                "weight": 100,
                "value": 4,
                "impact_score": 400,
                "impact_share_pct": 4.25,
            },
            {
                "rank": 3,
                "reason": "best_reason",
                "weight": 40,
                "value": "highest_total_score",
                "impact_score": 40,
                "impact_share_pct": 0.11,
            },
        ],
    },
    "decision_explanations": {
        **base["decision_explanations"],
        "best_vs_others": [
            {
                "winner_profile": "default",
                "challenger_profile": "industrial_strict",
                "score_margin": 4,
                "tie_on_total_score": False,
                "winner_advantages": ["recommended_component", "decision_component"],
                "score_breakdown_delta": {
                    "decision_component": 100,
                    "exit_component": 0,
                    "reasons_component": 0,
                    "recommended_component": 3,
                    "total_score": 103,
                },
                "ranked_advantages": [
                    {"component": "decision_component", "delta": 100},
                    {"component": "recommended_component", "delta": 3},
                ],
            }
        ],
    },
}

(root / "compare_incomplete.json").write_text(json.dumps(base, indent=2), encoding="utf-8")
(root / "compare_complete.json").write_text(json.dumps(complete, indent=2), encoding="utf-8")
PY

python3 -m gateforge.governance_promote_apply \
  --compare-summary artifacts/governance_promote_apply_explanation_structure_demo/compare_incomplete.json \
  --require-ranking-explanation-structure \
  --out artifacts/governance_promote_apply_explanation_structure_demo/apply_incomplete_needs_review.json \
  --report artifacts/governance_promote_apply_explanation_structure_demo/apply_incomplete_needs_review.md \
  --audit artifacts/governance_promote_apply_explanation_structure_demo/decision_audit.jsonl

set +e
python3 -m gateforge.governance_promote_apply \
  --compare-summary artifacts/governance_promote_apply_explanation_structure_demo/compare_incomplete.json \
  --require-ranking-explanation-structure \
  --strict-ranking-explanation-structure \
  --out artifacts/governance_promote_apply_explanation_structure_demo/apply_incomplete_strict_fail.json \
  --report artifacts/governance_promote_apply_explanation_structure_demo/apply_incomplete_strict_fail.md \
  --audit artifacts/governance_promote_apply_explanation_structure_demo/decision_audit.jsonl
STRICT_RC=$?
set -e

python3 -m gateforge.governance_promote_apply \
  --compare-summary artifacts/governance_promote_apply_explanation_structure_demo/compare_complete.json \
  --require-ranking-explanation-structure \
  --strict-ranking-explanation-structure \
  --out artifacts/governance_promote_apply_explanation_structure_demo/apply_complete_pass.json \
  --report artifacts/governance_promote_apply_explanation_structure_demo/apply_complete_pass.md \
  --audit artifacts/governance_promote_apply_explanation_structure_demo/decision_audit.jsonl

python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/governance_promote_apply_explanation_structure_demo")
needs_review = json.loads((root / "apply_incomplete_needs_review.json").read_text(encoding="utf-8"))
strict_fail = json.loads((root / "apply_incomplete_strict_fail.json").read_text(encoding="utf-8"))
pass_payload = json.loads((root / "apply_complete_pass.json").read_text(encoding="utf-8"))

flags = {
    "incomplete_expected_needs_review": "PASS"
    if needs_review.get("final_status") == "NEEDS_REVIEW"
    and "ranking_explanation_structure_invalid" in (needs_review.get("reasons") or [])
    else "FAIL",
    "incomplete_strict_expected_fail": "PASS"
    if strict_fail.get("final_status") == "FAIL"
    and "ranking_explanation_structure_invalid" in (strict_fail.get("reasons") or [])
    else "FAIL",
    "complete_expected_pass": "PASS"
    if pass_payload.get("final_status") == "PASS"
    and (pass_payload.get("ranking_explanation_structure_errors") or []) == []
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "incomplete_needs_review_status": needs_review.get("final_status"),
    "incomplete_strict_fail_status": strict_fail.get("final_status"),
    "complete_pass_status": pass_payload.get("final_status"),
    "incomplete_error_count": len(needs_review.get("ranking_explanation_structure_errors") or []),
    "complete_error_count": len(pass_payload.get("ranking_explanation_structure_errors") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(root / "summary.md").write_text(
    "\n".join(
        [
            "# Governance Promote Apply Explanation Structure Demo",
            "",
            f"- incomplete_needs_review_status: `{summary['incomplete_needs_review_status']}`",
            f"- incomplete_strict_fail_status: `{summary['incomplete_strict_fail_status']}`",
            f"- complete_pass_status: `{summary['complete_pass_status']}`",
            f"- incomplete_error_count: `{summary['incomplete_error_count']}`",
            f"- complete_error_count: `{summary['complete_error_count']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- incomplete_expected_needs_review: `{flags['incomplete_expected_needs_review']}`",
            f"- incomplete_strict_expected_fail: `{flags['incomplete_strict_expected_fail']}`",
            f"- complete_expected_pass: `{flags['complete_expected_pass']}`",
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
  echo "expected strict incomplete structure flow to exit 1, got $STRICT_RC" >&2
  exit 1
fi

cat artifacts/governance_promote_apply_explanation_structure_demo/summary.json
cat artifacts/governance_promote_apply_explanation_structure_demo/summary.md
