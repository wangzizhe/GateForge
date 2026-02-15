#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROMOTE_APPLY_REQUIRE_RANKING_EXPLANATION="${PROMOTE_APPLY_REQUIRE_RANKING_EXPLANATION:-0}"

mkdir -p artifacts/governance_promote_apply_demo
rm -f artifacts/governance_promote_apply_demo/*.json artifacts/governance_promote_apply_demo/*.md artifacts/governance_promote_apply_demo/*.jsonl

bash scripts/demo_governance_promote_compare.sh

cmd=(
  python3 -m gateforge.governance_promote_apply
  --compare-summary artifacts/governance_promote_compare_demo/summary_with_override.json
  --actor governance.bot
  --out artifacts/governance_promote_apply_demo/pass_apply.json
  --report artifacts/governance_promote_apply_demo/pass_apply.md
  --audit artifacts/governance_promote_apply_demo/decision_audit.jsonl
)
if [[ "$PROMOTE_APPLY_REQUIRE_RANKING_EXPLANATION" == "1" ]]; then
  cmd+=(--require-ranking-explanation)
fi
"${cmd[@]}"

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/governance_promote_compare_demo/summary_with_override.json").read_text(encoding="utf-8"))
payload["status"] = "NEEDS_REVIEW"
payload["best_decision"] = "NEEDS_REVIEW"
payload["constraint_reason"] = "top_score_margin_low"
Path("artifacts/governance_promote_apply_demo/synthetic_needs_review_compare.json").write_text(
    json.dumps(payload, indent=2),
    encoding="utf-8",
)
PY

set +e
cmd=(
  python3 -m gateforge.governance_promote_apply
  --compare-summary artifacts/governance_promote_apply_demo/synthetic_needs_review_compare.json
  --actor governance.bot
  --out artifacts/governance_promote_apply_demo/review_missing_ticket.json
  --report artifacts/governance_promote_apply_demo/review_missing_ticket.md
  --audit artifacts/governance_promote_apply_demo/decision_audit.jsonl
)
if [[ "$PROMOTE_APPLY_REQUIRE_RANKING_EXPLANATION" == "1" ]]; then
  cmd+=(--require-ranking-explanation)
fi
"${cmd[@]}"
MISSING_TICKET_RC=$?
set -e
if [[ "$MISSING_TICKET_RC" -ne 1 ]]; then
  echo "expected missing ticket flow to exit 1, got $MISSING_TICKET_RC" >&2
  exit 1
fi

cmd=(
  python3 -m gateforge.governance_promote_apply
  --compare-summary artifacts/governance_promote_apply_demo/synthetic_needs_review_compare.json
  --review-ticket-id REV-42
  --actor governance.bot
  --out artifacts/governance_promote_apply_demo/review_with_ticket.json
  --report artifacts/governance_promote_apply_demo/review_with_ticket.md
  --audit artifacts/governance_promote_apply_demo/decision_audit.jsonl
)
if [[ "$PROMOTE_APPLY_REQUIRE_RANKING_EXPLANATION" == "1" ]]; then
  cmd+=(--require-ranking-explanation)
fi
"${cmd[@]}"

python3 - <<'PY'
import json
from pathlib import Path

pass_payload = json.loads(Path("artifacts/governance_promote_apply_demo/pass_apply.json").read_text(encoding="utf-8"))
missing_ticket = json.loads(Path("artifacts/governance_promote_apply_demo/review_missing_ticket.json").read_text(encoding="utf-8"))
with_ticket = json.loads(Path("artifacts/governance_promote_apply_demo/review_with_ticket.json").read_text(encoding="utf-8"))
audit_rows = [
    json.loads(line)
    for line in Path("artifacts/governance_promote_apply_demo/decision_audit.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]

flags = {
    "pass_expected_promote": "PASS"
    if pass_payload.get("final_status") == "PASS" and pass_payload.get("apply_action") == "promote"
    else "FAIL",
    "missing_ticket_expected_fail": "PASS"
    if missing_ticket.get("final_status") == "FAIL"
    and "needs_review_ticket_required" in (missing_ticket.get("reasons") or [])
    else "FAIL",
    "with_ticket_expected_hold": "PASS"
    if with_ticket.get("final_status") == "NEEDS_REVIEW"
    and with_ticket.get("apply_action") == "hold_for_review"
    and with_ticket.get("review_ticket_id") == "REV-42"
    else "FAIL",
    "audit_rows_expected_3": "PASS" if len(audit_rows) == 3 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "require_ranking_explanation": pass_payload.get("require_ranking_explanation"),
    "pass_status": pass_payload.get("final_status"),
    "pass_ranking_selection_priority": pass_payload.get("ranking_selection_priority"),
    "pass_ranking_best_vs_others_count": len(pass_payload.get("ranking_best_vs_others") or []),
    "missing_ticket_status": missing_ticket.get("final_status"),
    "with_ticket_status": with_ticket.get("final_status"),
    "with_ticket_id": with_ticket.get("review_ticket_id"),
    "audit_row_count": len(audit_rows),
    "result_flags": flags,
    "bundle_status": bundle_status,
}

Path("artifacts/governance_promote_apply_demo/summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
Path("artifacts/governance_promote_apply_demo/summary.md").write_text(
    "\n".join(
        [
            "# Governance Promote Apply Demo",
            "",
            f"- require_ranking_explanation: `{summary.get('require_ranking_explanation')}`",
            f"- pass_status: `{summary['pass_status']}`",
            f"- pass_ranking_selection_priority: `{','.join(summary.get('pass_ranking_selection_priority') or [])}`",
            f"- pass_ranking_best_vs_others_count: `{summary['pass_ranking_best_vs_others_count']}`",
            f"- missing_ticket_status: `{summary['missing_ticket_status']}`",
            f"- with_ticket_status: `{summary['with_ticket_status']}`",
            f"- with_ticket_id: `{summary['with_ticket_id']}`",
            f"- audit_row_count: `{summary['audit_row_count']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- pass_expected_promote: `{flags['pass_expected_promote']}`",
            f"- missing_ticket_expected_fail: `{flags['missing_ticket_expected_fail']}`",
            f"- with_ticket_expected_hold: `{flags['with_ticket_expected_hold']}`",
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

cat artifacts/governance_promote_apply_demo/summary.json
cat artifacts/governance_promote_apply_demo/summary.md
