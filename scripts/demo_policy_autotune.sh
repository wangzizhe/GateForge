#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/policy_autotune_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

bash scripts/demo_governance_snapshot.sh >/dev/null
bash scripts/demo_mutation_dashboard.sh >/dev/null
bash scripts/demo_medium_pack_v1_dashboard.sh >/dev/null
bash scripts/demo_dataset_history.sh >/dev/null

python3 -m gateforge.policy_autotune_advisor \
  --governance-snapshot artifacts/governance_snapshot_demo/summary.json \
  --mutation-dashboard artifacts/mutation_dashboard_demo/summary.json \
  --medium-dashboard artifacts/benchmark_medium_v1/dashboard.json \
  --dataset-pipeline-summary artifacts/dataset_pipeline_demo/summary.json \
  --dataset-history-summary artifacts/dataset_history_demo/history_summary.json \
  --dataset-history-trend artifacts/dataset_history_demo/history_trend.json \
  --dataset-governance-summary artifacts/dataset_policy_lifecycle_demo/ledger_summary.json \
  --dataset-governance-trend artifacts/dataset_governance_history_demo/trend.json \
  --out "$OUT_DIR/advisor.json" \
  --report-out "$OUT_DIR/advisor.md"

cp policies/promote_apply/default.json "$OUT_DIR/policy.default.copy.json"

python3 -m gateforge.governance_policy_patch_proposal \
  --advisor-summary "$OUT_DIR/advisor.json" \
  --policy-path "$OUT_DIR/policy.default.copy.json" \
  --proposal-id policy-autotune-demo-001 \
  --out "$OUT_DIR/proposal.json" \
  --report "$OUT_DIR/proposal.md"

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

out = Path("artifacts/policy_autotune_demo")
advisor = json.loads((out / "advisor.json").read_text(encoding="utf-8"))
proposal = json.loads((out / "proposal.json").read_text(encoding="utf-8"))
apply_summary = json.loads((out / "apply.json").read_text(encoding="utf-8"))

advice = advisor.get("advice") or {}
flags = {
    "advisor_profile_present": "PASS" if isinstance(advice.get("suggested_policy_profile"), str) else "FAIL",
    "advisor_reasons_present": "PASS" if len(advice.get("reasons") or []) >= 1 else "FAIL",
    "proposal_created": "PASS" if proposal.get("proposal_id") == "policy-autotune-demo-001" else "FAIL",
    "apply_passed": "PASS" if apply_summary.get("final_status") == "PASS" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "advisor_profile": advice.get("suggested_policy_profile"),
    "advisor_confidence": advice.get("confidence"),
    "advisor_reasons_count": len(advice.get("reasons") or []),
    "proposal_change_count": proposal.get("change_count"),
    "apply_final_status": apply_summary.get("final_status"),
    "apply_action": apply_summary.get("apply_action"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Policy Auto-Tune Demo",
            "",
            f"- advisor_profile: `{summary['advisor_profile']}`",
            f"- advisor_confidence: `{summary['advisor_confidence']}`",
            f"- advisor_reasons_count: `{summary['advisor_reasons_count']}`",
            f"- proposal_change_count: `{summary['proposal_change_count']}`",
            f"- apply_final_status: `{summary['apply_final_status']}`",
            f"- apply_action: `{summary['apply_action']}`",
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
print(json.dumps({"bundle_status": bundle_status, "apply_final_status": summary["apply_final_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
