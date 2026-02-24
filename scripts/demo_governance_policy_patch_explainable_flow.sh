#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/governance_policy_patch_explainable_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

cat > "$OUT_DIR/snapshot.json" <<'JSON'
{
  "kpis": {
    "risk_score": 68,
    "latest_mismatch_count": 2
  },
  "risks": ["replay_risk_level_high"]
}
JSON

cat > "$OUT_DIR/trend.json" <<'JSON'
{
  "trend": {
    "kpi_delta": {
      "history_mismatch_total_delta": 3,
      "risk_score_delta": 9
    }
  }
}
JSON

cat > "$OUT_DIR/compare.json" <<'JSON'
{
  "top_score_margin": 1,
  "explanation_completeness": 82,
  "decision_explanation_leaderboard": [
    {
      "profile": "default",
      "pairwise_net_margin": 1
    }
  ]
}
JSON

python3 -m gateforge.governance_policy_advisor \
  --snapshot "$OUT_DIR/snapshot.json" \
  --trend "$OUT_DIR/trend.json" \
  --compare-summary "$OUT_DIR/compare.json" \
  --out "$OUT_DIR/advisor.json" \
  --report "$OUT_DIR/advisor.md"

cp policies/promote_apply/default.json "$OUT_DIR/policy.default.copy.json"

python3 -m gateforge.governance_policy_patch_proposal \
  --advisor-summary "$OUT_DIR/advisor.json" \
  --policy-path "$OUT_DIR/policy.default.copy.json" \
  --proposal-id governance-policy-explainable-001 \
  --out "$OUT_DIR/proposal.json" \
  --report "$OUT_DIR/proposal.md"

python3 -m gateforge.governance_policy_patch_apply \
  --proposal "$OUT_DIR/proposal.json" \
  --preview-only \
  --out "$OUT_DIR/preview.json" \
  --report "$OUT_DIR/preview.md"

cat > "$OUT_DIR/approval.approve.json" <<'JSON'
{
  "decision": "approve",
  "reviewer": "human.reviewer"
}
JSON

python3 -m gateforge.governance_policy_patch_apply \
  --proposal "$OUT_DIR/proposal.json" \
  --approval "$OUT_DIR/approval.approve.json" \
  --apply \
  --out "$OUT_DIR/apply.json" \
  --report "$OUT_DIR/apply.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/governance_policy_patch_explainable_demo")
advisor = json.loads((out / "advisor.json").read_text(encoding="utf-8"))
proposal = json.loads((out / "proposal.json").read_text(encoding="utf-8"))
preview = json.loads((out / "preview.json").read_text(encoding="utf-8"))
apply_summary = json.loads((out / "apply.json").read_text(encoding="utf-8"))

advice = advisor.get("advice", {})
why_now = advice.get("why_now", {})
scorecard = advice.get("recommendation_scorecard", {})
flags = {
    "advisor_why_now_present": "PASS" if isinstance(why_now.get("summary"), str) and isinstance(why_now.get("urgency"), str) else "FAIL",
    "advisor_scorecard_present": "PASS" if isinstance(scorecard.get("impact"), str) and isinstance(scorecard.get("priority"), str) else "FAIL",
    "proposal_has_advisor_context": "PASS" if isinstance(proposal.get("advisor_why_now"), dict) and isinstance(proposal.get("advisor_recommendation_scorecard"), dict) else "FAIL",
    "preview_status_is_preview": "PASS" if preview.get("final_status") == "PREVIEW" else "FAIL",
    "preview_has_impacts": "PASS" if isinstance(preview.get("impact_preview"), list) and len(preview.get("impact_preview")) >= 1 else "FAIL",
    "apply_passed": "PASS" if apply_summary.get("final_status") == "PASS" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "proposal_id": proposal.get("proposal_id"),
    "why_now_urgency": why_now.get("urgency"),
    "scorecard_priority": scorecard.get("priority"),
    "proposal_change_count": proposal.get("change_count"),
    "preview_status": preview.get("final_status"),
    "apply_status": apply_summary.get("final_status"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Governance Policy Patch Explainable Flow Demo",
            "",
            f"- proposal_id: `{summary['proposal_id']}`",
            f"- why_now_urgency: `{summary['why_now_urgency']}`",
            f"- scorecard_priority: `{summary['scorecard_priority']}`",
            f"- proposal_change_count: `{summary['proposal_change_count']}`",
            f"- preview_status: `{summary['preview_status']}`",
            f"- apply_status: `{summary['apply_status']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "proposal_id": summary.get("proposal_id")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
