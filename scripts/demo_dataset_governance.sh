#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_governance_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

bash scripts/demo_dataset_history.sh >/dev/null

python3 -m gateforge.dataset_policy_advisor \
  --dataset-history-summary artifacts/dataset_history_demo/history_summary.json \
  --dataset-history-trend artifacts/dataset_history_demo/history_trend.json \
  --policy-profile default \
  --out "$OUT_DIR/advisor.json" \
  --report-out "$OUT_DIR/advisor.md"

python3 -m gateforge.dataset_policy_patch_proposal \
  --advisor-summary "$OUT_DIR/advisor.json" \
  --policy-profile default \
  --proposal-id dataset-governance-demo-001 \
  --out "$OUT_DIR/proposal.json" \
  --report "$OUT_DIR/proposal.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_governance_demo")
advisor = json.loads((out / "advisor.json").read_text(encoding="utf-8"))
proposal = json.loads((out / "proposal.json").read_text(encoding="utf-8"))

advice = advisor.get("advice") if isinstance(advisor.get("advice"), dict) else {}
flags = {
    "advisor_present": "PASS" if isinstance(advice.get("suggested_action"), str) else "FAIL",
    "proposal_created": "PASS" if proposal.get("proposal_id") == "dataset-governance-demo-001" else "FAIL",
    "proposal_has_policy_after": "PASS" if isinstance(proposal.get("policy_after"), dict) else "FAIL",
}

bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "advisor_action": advice.get("suggested_action"),
    "advisor_profile": advice.get("suggested_policy_profile"),
    "advisor_confidence": advice.get("confidence"),
    "proposal_change_count": proposal.get("change_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}

(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Dataset Governance Demo",
            "",
            f"- advisor_action: `{summary['advisor_action']}`",
            f"- advisor_profile: `{summary['advisor_profile']}`",
            f"- advisor_confidence: `{summary['advisor_confidence']}`",
            f"- proposal_change_count: `{summary['proposal_change_count']}`",
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
print(json.dumps({"bundle_status": bundle_status, "advisor_action": summary["advisor_action"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
