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
}
with_explain = {
    "status": "PASS",
    "best_profile": "default",
    "best_decision": "PASS",
    "recommended_profile": "default",
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
}
(root / "compare_without_explanation.json").write_text(json.dumps(without_explain, indent=2), encoding="utf-8")
(root / "compare_with_explanation.json").write_text(json.dumps(with_explain, indent=2), encoding="utf-8")
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
  --out artifacts/governance_promote_apply_strict_guard_demo/apply_with_explanation.json \
  --report artifacts/governance_promote_apply_strict_guard_demo/apply_with_explanation.md \
  --audit artifacts/governance_promote_apply_strict_guard_demo/decision_audit.jsonl

python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/governance_promote_apply_strict_guard_demo")
without = json.loads((root / "apply_without_explanation.json").read_text(encoding="utf-8"))
with_explain = json.loads((root / "apply_with_explanation.json").read_text(encoding="utf-8"))
audit_rows = [json.loads(x) for x in (root / "decision_audit.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]

flags = {
    "without_expected_fail": "PASS"
    if without.get("final_status") == "FAIL" and "ranking_explanation_required" in (without.get("reasons") or [])
    else "FAIL",
    "with_expected_pass": "PASS"
    if with_explain.get("final_status") == "PASS" and with_explain.get("apply_action") == "promote"
    else "FAIL",
    "audit_rows_expected_2": "PASS" if len(audit_rows) == 2 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "without_explanation_status": without.get("final_status"),
    "with_explanation_status": with_explain.get("final_status"),
    "with_explanation_apply_action": with_explain.get("apply_action"),
    "with_explanation_has_ranking": bool(with_explain.get("ranking_best_vs_others")),
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
            f"- audit_row_count: `{summary['audit_row_count']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- without_expected_fail: `{flags['without_expected_fail']}`",
            f"- with_expected_pass: `{flags['with_expected_pass']}`",
            f"- audit_rows_expected_2: `{flags['audit_rows_expected_2']}`",
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

cat artifacts/governance_promote_apply_strict_guard_demo/summary.json
cat artifacts/governance_promote_apply_strict_guard_demo/summary.md
