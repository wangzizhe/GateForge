#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/mutation_policy_patch_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

bash scripts/demo_mutation_dashboard.sh >/dev/null

python3 -m gateforge.mutation_policy_advisor \
  --dashboard artifacts/mutation_dashboard_demo/summary.json \
  --out "$OUT_DIR/advisor.json" \
  --report-out "$OUT_DIR/advisor.md"

cp policies/promote_apply/default.json "$OUT_DIR/policy.default.copy.json"

python3 -m gateforge.governance_policy_patch_proposal \
  --advisor-summary "$OUT_DIR/advisor.json" \
  --policy-path "$OUT_DIR/policy.default.copy.json" \
  --proposal-id mutation-policy-patch-demo-001 \
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

out = Path("artifacts/mutation_policy_patch_demo")
advisor = json.loads((out / "advisor.json").read_text(encoding="utf-8"))
proposal = json.loads((out / "proposal.json").read_text(encoding="utf-8"))
apply_summary = json.loads((out / "apply.json").read_text(encoding="utf-8"))

flags = {
    "advisor_present": "PASS" if isinstance((advisor.get("advice") or {}).get("suggested_policy_profile"), str) else "FAIL",
    "proposal_created": "PASS" if proposal.get("proposal_id") == "mutation-policy-patch-demo-001" else "FAIL",
    "apply_passed": "PASS" if apply_summary.get("final_status") == "PASS" else "FAIL",
    "policy_applied": "PASS" if apply_summary.get("applied") is True else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "advisor_profile": (advisor.get("advice") or {}).get("suggested_policy_profile"),
    "advisor_confidence": (advisor.get("advice") or {}).get("confidence"),
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
            "# Mutation Policy Patch Demo",
            "",
            f"- advisor_profile: `{summary['advisor_profile']}`",
            f"- advisor_confidence: `{summary['advisor_confidence']}`",
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
