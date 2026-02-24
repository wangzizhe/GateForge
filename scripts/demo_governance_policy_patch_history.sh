#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/governance_policy_patch_history_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

bash scripts/demo_governance_policy_patch_apply.sh >/dev/null

python3 -m gateforge.governance_policy_patch_history \
  --record artifacts/governance_policy_patch_apply_demo/apply.no_approval.json \
  --record artifacts/governance_policy_patch_apply_demo/apply.reject.json \
  --record artifacts/governance_policy_patch_apply_demo/apply.approve_apply.json \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/summary.json" \
  --report "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/governance_policy_patch_history_demo")
summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))

status_counts = summary.get("status_counts", {})
flags = {
    "has_three_records": "PASS" if summary.get("total_records") == 3 else "FAIL",
    "has_pass_count": "PASS" if status_counts.get("PASS") == 1 else "FAIL",
    "has_needs_review_count": "PASS" if status_counts.get("NEEDS_REVIEW") == 1 else "FAIL",
    "has_fail_count": "PASS" if status_counts.get("FAIL") == 1 else "FAIL",
    "has_applied_count": "PASS" if summary.get("applied_count") == 1 else "FAIL",
    "has_reject_count": "PASS" if summary.get("reject_count") == 1 else "FAIL",
    "has_pairwise_threshold_enabled_count": "PASS"
    if isinstance(summary.get("pairwise_threshold_enabled_count"), int)
    else "FAIL",
    "has_latest_pairwise_threshold_field": "PASS"
    if "latest_pairwise_threshold" in summary
    else "FAIL",
    "latest_is_pass": "PASS" if summary.get("latest_status") == "PASS" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

demo_summary = {
    "total_records": summary.get("total_records"),
    "latest_status": summary.get("latest_status"),
    "status_counts": status_counts,
    "applied_count": summary.get("applied_count"),
    "reject_count": summary.get("reject_count"),
    "pairwise_threshold_enabled_count": summary.get("pairwise_threshold_enabled_count"),
    "latest_pairwise_threshold": summary.get("latest_pairwise_threshold"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(root / "demo_summary.json").write_text(json.dumps(demo_summary, indent=2), encoding="utf-8")
(root / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Governance Policy Patch History Demo",
            "",
            f"- total_records: `{demo_summary['total_records']}`",
            f"- latest_status: `{demo_summary['latest_status']}`",
            f"- pass_count: `{status_counts.get('PASS', 0)}`",
            f"- needs_review_count: `{status_counts.get('NEEDS_REVIEW', 0)}`",
            f"- fail_count: `{status_counts.get('FAIL', 0)}`",
            f"- applied_count: `{demo_summary['applied_count']}`",
            f"- reject_count: `{demo_summary['reject_count']}`",
            f"- pairwise_threshold_enabled_count: `{demo_summary['pairwise_threshold_enabled_count']}`",
            f"- latest_pairwise_threshold: `{demo_summary['latest_pairwise_threshold']}`",
            f"- bundle_status: `{demo_summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- has_three_records: `{flags['has_three_records']}`",
            f"- has_pass_count: `{flags['has_pass_count']}`",
            f"- has_needs_review_count: `{flags['has_needs_review_count']}`",
            f"- has_fail_count: `{flags['has_fail_count']}`",
            f"- has_applied_count: `{flags['has_applied_count']}`",
            f"- has_reject_count: `{flags['has_reject_count']}`",
            f"- has_pairwise_threshold_enabled_count: `{flags['has_pairwise_threshold_enabled_count']}`",
            f"- has_latest_pairwise_threshold_field: `{flags['has_latest_pairwise_threshold_field']}`",
            f"- latest_is_pass: `{flags['latest_is_pass']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
