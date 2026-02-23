#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/governance_policy_patch_apply_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

bash scripts/demo_governance_policy_advisor_bundle.sh >/dev/null

cp policies/promote_apply/default.json "$OUT_DIR/policy.default.copy.json"

python3 -m gateforge.governance_policy_patch_proposal \
  --advisor-summary artifacts/governance_policy_advisor_bundle_demo/policy_advice.json \
  --policy-path "$OUT_DIR/policy.default.copy.json" \
  --proposal-id policy-patch-demo-001 \
  --out "$OUT_DIR/proposal.json" \
  --report "$OUT_DIR/proposal.md"

cat > "$OUT_DIR/approval.reject.json" <<'JSON'
{
  "decision": "reject",
  "reviewer": "human.reviewer"
}
JSON

cat > "$OUT_DIR/approval.approve.json" <<'JSON'
{
  "decision": "approve",
  "reviewer": "human.reviewer"
}
JSON

python3 -m gateforge.governance_policy_patch_apply \
  --proposal "$OUT_DIR/proposal.json" \
  --out "$OUT_DIR/apply.no_approval.json" \
  --report "$OUT_DIR/apply.no_approval.md"

set +e
python3 -m gateforge.governance_policy_patch_apply \
  --proposal "$OUT_DIR/proposal.json" \
  --approval "$OUT_DIR/approval.reject.json" \
  --out "$OUT_DIR/apply.reject.json" \
  --report "$OUT_DIR/apply.reject.md"
REJECT_RC=$?
set -e
echo "$REJECT_RC" > "$OUT_DIR/reject.rc"

python3 -m gateforge.governance_policy_patch_apply \
  --proposal "$OUT_DIR/proposal.json" \
  --approval "$OUT_DIR/approval.approve.json" \
  --out "$OUT_DIR/apply.approve_hold.json" \
  --report "$OUT_DIR/apply.approve_hold.md"

python3 -m gateforge.governance_policy_patch_apply \
  --proposal "$OUT_DIR/proposal.json" \
  --approval "$OUT_DIR/approval.approve.json" \
  --apply \
  --out "$OUT_DIR/apply.approve_apply.json" \
  --report "$OUT_DIR/apply.approve_apply.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/governance_policy_patch_apply_demo")
proposal = json.loads((out / "proposal.json").read_text(encoding="utf-8"))
no_approval = json.loads((out / "apply.no_approval.json").read_text(encoding="utf-8"))
reject = json.loads((out / "apply.reject.json").read_text(encoding="utf-8"))
approve_hold = json.loads((out / "apply.approve_hold.json").read_text(encoding="utf-8"))
approve_apply = json.loads((out / "apply.approve_apply.json").read_text(encoding="utf-8"))
updated_policy = json.loads((out / "policy.default.copy.json").read_text(encoding="utf-8"))

flags = {
    "proposal_created": "PASS" if proposal.get("proposal_id") == "policy-patch-demo-001" else "FAIL",
    "no_approval_needs_review": "PASS" if no_approval.get("final_status") == "NEEDS_REVIEW" else "FAIL",
    "reject_failed": "PASS" if reject.get("final_status") == "FAIL" else "FAIL",
    "approve_hold_needs_review": "PASS" if approve_hold.get("final_status") == "NEEDS_REVIEW" else "FAIL",
    "approve_apply_passed": "PASS" if approve_apply.get("final_status") == "PASS" else "FAIL",
    "apply_status_changed": "PASS" if approve_apply.get("applied") is True else "FAIL",
    "policy_written": "PASS" if isinstance(updated_policy, dict) and updated_policy else "FAIL",
}

bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "proposal_id": proposal.get("proposal_id"),
    "change_count": proposal.get("change_count"),
    "reject_exit_code": int(Path("artifacts/governance_policy_patch_apply_demo/reject.rc").read_text(encoding="utf-8")) if Path("artifacts/governance_policy_patch_apply_demo/reject.rc").exists() else None,
    "statuses": {
        "no_approval": no_approval.get("final_status"),
        "reject": reject.get("final_status"),
        "approve_hold": approve_hold.get("final_status"),
        "approve_apply": approve_apply.get("final_status"),
    },
    "applied": approve_apply.get("applied"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}

(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Governance Policy Patch Apply Demo",
            "",
            f"- proposal_id: `{summary['proposal_id']}`",
            f"- change_count: `{summary['change_count']}`",
            f"- no_approval_status: `{summary['statuses']['no_approval']}`",
            f"- reject_status: `{summary['statuses']['reject']}`",
            f"- approve_hold_status: `{summary['statuses']['approve_hold']}`",
            f"- approve_apply_status: `{summary['statuses']['approve_apply']}`",
            f"- applied: `{summary['applied']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- proposal_created: `{flags['proposal_created']}`",
            f"- no_approval_needs_review: `{flags['no_approval_needs_review']}`",
            f"- reject_failed: `{flags['reject_failed']}`",
            f"- approve_hold_needs_review: `{flags['approve_hold_needs_review']}`",
            f"- approve_apply_passed: `{flags['approve_apply_passed']}`",
            f"- apply_status_changed: `{flags['apply_status_changed']}`",
            f"- policy_written: `{flags['policy_written']}`",
            "",
        ]
    ),
    encoding="utf-8",
)

print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
if [[ "$REJECT_RC" -ne 1 ]]; then
  echo "unexpected reject apply exit code: $REJECT_RC" >&2
  exit 1
fi

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
