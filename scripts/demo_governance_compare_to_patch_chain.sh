#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/governance_compare_to_patch_chain_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

cat > "$OUT_DIR/snapshot.json" <<'JSON'
{
  "kpis": {
    "risk_score": 65,
    "latest_mismatch_count": 2
  },
  "risks": ["replay_risk_level_high"]
}
JSON

cat > "$OUT_DIR/trend.json" <<'JSON'
{
  "trend": {
    "kpi_delta": {
      "history_mismatch_total_delta": 2,
      "risk_score_delta": 7
    }
  }
}
JSON

cat > "$OUT_DIR/compare.json" <<'JSON'
{
  "status": "PASS",
  "best_profile": "default",
  "best_decision": "PASS",
  "recommended_profile": "default",
  "best_reason": "highest_total_score",
  "top_score_margin": 1,
  "explanation_completeness": 82,
  "decision_explanation_leaderboard": [
    {
      "profile": "default",
      "pairwise_net_margin": 1
    }
  ],
  "decision_explanation_ranking_details": {
    "top_driver": "component_delta:recommended_component",
    "numeric_reason_count": 1,
    "drivers": [
      {
        "rank": 1,
        "reason": "component_delta:recommended_component",
        "weight": 90,
        "value": 3,
        "impact_score": 270,
        "impact_share_pct": 72.2
      }
    ]
  }
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
  --proposal-id governance-compare-chain-001 \
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
  "reviewer": "human.reviewer",
  "review_id": "governance-compare-chain-review-001"
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

out = Path("artifacts/governance_compare_to_patch_chain_demo")
advisor = json.loads((out / "advisor.json").read_text(encoding="utf-8"))
proposal = json.loads((out / "proposal.json").read_text(encoding="utf-8"))
preview = json.loads((out / "preview.json").read_text(encoding="utf-8"))
apply_summary = json.loads((out / "apply.json").read_text(encoding="utf-8"))

advice = advisor.get("advice", {})
signal = advice.get("ranking_driver_signal", {}) if isinstance(advice.get("ranking_driver_signal"), dict) else {}
flags = {
    "advisor_has_driver_signal": "PASS" if isinstance(signal.get("top_driver"), str) else "FAIL",
    "proposal_carries_driver_signal": "PASS"
    if isinstance((proposal.get("advisor_ranking_driver_signal") or {}).get("top_driver"), str)
    else "FAIL",
    "preview_status_ok": "PASS" if preview.get("final_status") == "PREVIEW" else "FAIL",
    "apply_status_ok": "PASS" if apply_summary.get("final_status") == "PASS" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "proposal_id": proposal.get("proposal_id"),
    "advisor_suggested_policy_profile": advice.get("suggested_policy_profile"),
    "advisor_top_driver": signal.get("top_driver"),
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
            "# Governance Compare-to-Patch Chain Demo",
            "",
            f"- proposal_id: `{summary['proposal_id']}`",
            f"- advisor_suggested_policy_profile: `{summary['advisor_suggested_policy_profile']}`",
            f"- advisor_top_driver: `{summary['advisor_top_driver']}`",
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
