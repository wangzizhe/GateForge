#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_promote_apply_strict_guard_demo
rm -f artifacts/governance_promote_apply_strict_guard_demo/*.json artifacts/governance_promote_apply_strict_guard_demo/*.md artifacts/governance_promote_apply_strict_guard_demo/*.jsonl

python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/governance_promote_apply_strict_guard_demo")
without_explain = {
    "status": "PASS",
    "best_profile": "default",
    "best_decision": "PASS",
    "recommended_profile": "default",
    "top_score_margin": 10,
}
with_explain = {
    "status": "PASS",
    "best_profile": "default",
    "best_decision": "PASS",
    "recommended_profile": "default",
    "top_score_margin": 10,
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
                "winner_total_score": 100,
                "challenger_total_score": 90,
                "score_margin": 10,
                "tie_on_total_score": False,
                "winner_advantages": ["decision_component", "reasons_component"],
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
with_explain_low_quality = {
    **with_explain,
    "explanation_quality": {
        "score": 60,
        "checks": {
            "has_selection_priority": True,
            "has_pairwise_rows": True,
            "all_pairwise_have_margin": True,
            "all_pairwise_have_profiles": True,
            "pairwise_advantages_non_empty": True,
        },
    },
}
(root / "compare_without_explanation.json").write_text(json.dumps(without_explain, indent=2), encoding="utf-8")
(root / "compare_with_explanation.json").write_text(json.dumps(with_explain, indent=2), encoding="utf-8")
(root / "compare_with_explanation_low_quality.json").write_text(
    json.dumps(with_explain_low_quality, indent=2), encoding="utf-8"
)
PY

set +e
python3 -m gateforge.governance_promote_apply \
  --compare-summary artifacts/governance_promote_apply_strict_guard_demo/compare_without_explanation.json \
  --require-ranking-explanation \
  --out artifacts/governance_promote_apply_strict_guard_demo/apply_without_explanation.json \
  --report artifacts/governance_promote_apply_strict_guard_demo/apply_without_explanation.md \
  --audit artifacts/governance_promote_apply_strict_guard_demo/decision_audit.jsonl
WITHOUT_RC=$?
set -e

python3 -m gateforge.governance_promote_apply \
  --compare-summary artifacts/governance_promote_apply_strict_guard_demo/compare_with_explanation.json \
  --require-ranking-explanation \
  --require-min-explanation-quality 80 \
  --out artifacts/governance_promote_apply_strict_guard_demo/apply_with_explanation.json \
  --report artifacts/governance_promote_apply_strict_guard_demo/apply_with_explanation.md \
  --audit artifacts/governance_promote_apply_strict_guard_demo/decision_audit.jsonl

set +e
python3 -m gateforge.governance_promote_apply \
  --compare-summary artifacts/governance_promote_apply_strict_guard_demo/compare_with_explanation_low_quality.json \
  --require-ranking-explanation \
  --require-min-explanation-quality 80 \
  --out artifacts/governance_promote_apply_strict_guard_demo/apply_with_low_quality.json \
  --report artifacts/governance_promote_apply_strict_guard_demo/apply_with_low_quality.md \
  --audit artifacts/governance_promote_apply_strict_guard_demo/decision_audit.jsonl
LOW_QUALITY_RC=$?
set -e

python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/governance_promote_apply_strict_guard_demo")
without = json.loads((root / "apply_without_explanation.json").read_text(encoding="utf-8"))
with_explain = json.loads((root / "apply_with_explanation.json").read_text(encoding="utf-8"))
with_low_quality = json.loads((root / "apply_with_low_quality.json").read_text(encoding="utf-8"))
audit_rows = [json.loads(x) for x in (root / "decision_audit.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]

flags = {
    "without_expected_fail": "PASS"
    if without.get("final_status") == "FAIL" and "ranking_explanation_required" in (without.get("reasons") or [])
    else "FAIL",
    "with_expected_pass": "PASS"
    if with_explain.get("final_status") == "PASS" and with_explain.get("apply_action") == "promote"
    else "FAIL",
    "low_quality_expected_fail": "PASS"
    if with_low_quality.get("final_status") == "FAIL"
    and "explanation_quality_below_required" in (with_low_quality.get("reasons") or [])
    else "FAIL",
    "audit_rows_expected_3": "PASS" if len(audit_rows) == 3 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "without_explanation_status": without.get("final_status"),
    "with_explanation_status": with_explain.get("final_status"),
    "with_explanation_apply_action": with_explain.get("apply_action"),
    "with_explanation_has_ranking": bool(with_explain.get("ranking_best_vs_others")),
    "with_low_quality_status": with_low_quality.get("final_status"),
    "with_low_quality_reasons": with_low_quality.get("reasons", []),
    "audit_row_count": len(audit_rows),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(root / "summary.md").write_text(
    "\n".join(
        [
            "# Governance Promote Apply Strict Guard Demo",
            "",
            f"- without_explanation_status: `{summary['without_explanation_status']}`",
            f"- with_explanation_status: `{summary['with_explanation_status']}`",
            f"- with_explanation_apply_action: `{summary['with_explanation_apply_action']}`",
            f"- with_explanation_has_ranking: `{summary['with_explanation_has_ranking']}`",
            f"- with_low_quality_status: `{summary['with_low_quality_status']}`",
            f"- audit_row_count: `{summary['audit_row_count']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- without_expected_fail: `{flags['without_expected_fail']}`",
            f"- with_expected_pass: `{flags['with_expected_pass']}`",
            f"- low_quality_expected_fail: `{flags['low_quality_expected_fail']}`",
            f"- audit_rows_expected_3: `{flags['audit_rows_expected_3']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

if [[ "$WITHOUT_RC" -ne 1 ]]; then
  echo "expected strict apply without explanation to exit 1, got $WITHOUT_RC" >&2
  exit 1
fi
if [[ "$LOW_QUALITY_RC" -ne 1 ]]; then
  echo "expected strict apply with low explanation quality to exit 1, got $LOW_QUALITY_RC" >&2
  exit 1
fi

cat artifacts/governance_promote_apply_strict_guard_demo/summary.json
cat artifacts/governance_promote_apply_strict_guard_demo/summary.md
