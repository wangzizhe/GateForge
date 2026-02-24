#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/governance_promote_compare_validate_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/governance_promote_compare_validate_demo")
good = {
    "status": "PASS",
    "best_profile": "default",
    "best_decision": "PASS",
    "recommended_profile": "default",
    "top_score_margin": 4,
    "decision_explanations": {
        "selection_priority": ["total_score", "decision"],
        "best_vs_others": [
            {
                "winner_profile": "default",
                "challenger_profile": "industrial_strict",
                "score_margin": 4,
                "tie_on_total_score": False,
                "winner_advantages": ["decision_component"],
                "score_breakdown_delta": {
                    "decision_component": 100,
                    "exit_component": 0,
                    "reasons_component": 0,
                    "recommended_component": 1,
                    "total_score": 101,
                },
                "ranked_advantages": [{"component": "decision_component", "delta": 100}],
            }
        ],
    },
    "decision_explanation_leaderboard": [{"profile": "default", "pairwise_net_margin": 4}],
    "decision_explanation_ranked": [
        {"reason": "top_score_margin", "weight": 100, "value": 4},
        {"reason": "best_reason", "weight": 10, "value": "highest_total_score"},
    ],
    "decision_explanation_ranking_details": {
        "top_driver": "top_score_margin",
        "numeric_reason_count": 1,
        "drivers": [
            {
                "rank": 1,
                "reason": "top_score_margin",
                "weight": 100,
                "value": 4,
                "impact_score": 400,
                "impact_share_pct": 100.0,
            }
        ],
    },
    "explanation_completeness": 100,
    "explanation_quality": {"score": 100},
}
bad = {
    "status": "PASS",
    "best_profile": "default",
    "best_decision": "PASS",
    "decision_explanations": {"selection_priority": ["total_score"], "best_vs_others": []},
}
(out / "good.json").write_text(json.dumps(good, indent=2), encoding="utf-8")
(out / "bad.json").write_text(json.dumps(bad, indent=2), encoding="utf-8")
PY

python3 -m gateforge.governance_promote_compare_validate \
  --in "$OUT_DIR/good.json" \
  --require-apply-ready > "$OUT_DIR/good.validate.json"

set +e
python3 -m gateforge.governance_promote_compare_validate \
  --in "$OUT_DIR/bad.json" \
  --require-apply-ready > "$OUT_DIR/bad.validate.json"
BAD_RC=$?
set -e
echo "$BAD_RC" > "$OUT_DIR/bad.rc"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/governance_promote_compare_validate_demo")
good = json.loads((out / "good.validate.json").read_text(encoding="utf-8"))
bad = json.loads((out / "bad.validate.json").read_text(encoding="utf-8"))
bad_rc = int((out / "bad.rc").read_text(encoding="utf-8")) if (out / "bad.rc").exists() else None

flags = {
    "good_expected_pass": "PASS" if good.get("status") == "PASS" else "FAIL",
    "bad_expected_fail": "PASS" if bad.get("status") == "FAIL" else "FAIL",
    "bad_expected_exit_1": "PASS" if bad_rc == 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "good_status": good.get("status"),
    "bad_status": bad.get("status"),
    "bad_errors_count": len(bad.get("errors") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Governance Promote Compare Validate Demo",
            "",
            f"- good_status: `{summary['good_status']}`",
            f"- bad_status: `{summary['bad_status']}`",
            f"- bad_errors_count: `{summary['bad_errors_count']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- good_expected_pass: `{flags['good_expected_pass']}`",
            f"- bad_expected_fail: `{flags['bad_expected_fail']}`",
            f"- bad_expected_exit_1: `{flags['bad_expected_exit_1']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

if [[ "$BAD_RC" -ne 1 ]]; then
  echo "expected bad validation exit code 1, got $BAD_RC" >&2
  exit 1
fi

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
