#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/governance_decision_bundle_v1"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

bash scripts/demo_governance_promote_compare.sh >/dev/null

python3 -m gateforge.governance_promote_apply \
  --compare-summary artifacts/governance_promote_compare_demo/summary.json \
  --policy-profile default \
  --require-ranking-explanation-structure \
  --out "$OUT_DIR/apply_summary.json" \
  --report "$OUT_DIR/apply_summary.md" \
  --audit "$OUT_DIR/apply_audit.jsonl"

bash scripts/demo_governance_policy_advisor_bundle.sh >/dev/null

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/governance_decision_bundle_v1")
compare = json.loads(Path("artifacts/governance_promote_compare_demo/summary.json").read_text(encoding="utf-8"))
apply_summary = json.loads((out / "apply_summary.json").read_text(encoding="utf-8"))
advisor_bundle = json.loads(
    Path("artifacts/governance_policy_advisor_bundle_demo/summary.json").read_text(encoding="utf-8")
)

flags = {
    "compare_status_present": "PASS" if compare.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "compare_best_profile_present": "PASS" if isinstance(compare.get("best_profile"), str) else "FAIL",
    "apply_status_present": "PASS" if apply_summary.get("final_status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "advisor_profile_present": "PASS" if isinstance(advisor_bundle.get("suggested_policy_profile"), str) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "compare_status": compare.get("status"),
    "compare_best_profile": compare.get("best_profile"),
    "compare_explanation_completeness": compare.get("explanation_completeness"),
    "apply_final_status": apply_summary.get("final_status"),
    "apply_action": apply_summary.get("apply_action"),
    "apply_reasons_count": len(apply_summary.get("reasons") or []),
    "advisor_suggested_policy_profile": advisor_bundle.get("suggested_policy_profile"),
    "advisor_confidence": advisor_bundle.get("advice_confidence"),
    "advisor_reasons_count": advisor_bundle.get("advice_reasons_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}

(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Governance Decision Bundle v1",
            "",
            f"- compare_status: `{summary['compare_status']}`",
            f"- compare_best_profile: `{summary['compare_best_profile']}`",
            f"- compare_explanation_completeness: `{summary['compare_explanation_completeness']}`",
            f"- apply_final_status: `{summary['apply_final_status']}`",
            f"- apply_action: `{summary['apply_action']}`",
            f"- apply_reasons_count: `{summary['apply_reasons_count']}`",
            f"- advisor_suggested_policy_profile: `{summary['advisor_suggested_policy_profile']}`",
            f"- advisor_confidence: `{summary['advisor_confidence']}`",
            f"- advisor_reasons_count: `{summary['advisor_reasons_count']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- compare_status_present: `{flags['compare_status_present']}`",
            f"- compare_best_profile_present: `{flags['compare_best_profile_present']}`",
            f"- apply_status_present: `{flags['apply_status_present']}`",
            f"- advisor_profile_present: `{flags['advisor_profile_present']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "apply_status": summary["apply_final_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
