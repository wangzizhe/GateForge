#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_policy_patch_advisor_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/failure_taxonomy_coverage_summary.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "missing_failure_types": ["stability_regression"],
  "missing_model_scales": ["large"]
}
JSON

cat > "$OUT_DIR/failure_distribution_benchmark_summary.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "detection_rate_after": 0.72,
  "false_positive_rate_after": 0.14,
  "regression_rate_after": 0.21,
  "distribution_drift_score": 0.41
}
JSON

cat > "$OUT_DIR/model_scale_ladder_summary.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "large_ready": false
}
JSON

python3 -m gateforge.dataset_failure_policy_patch_advisor \
  --failure-taxonomy-coverage "$OUT_DIR/failure_taxonomy_coverage_summary.json" \
  --failure-distribution-benchmark "$OUT_DIR/failure_distribution_benchmark_summary.json" \
  --model-scale-ladder "$OUT_DIR/model_scale_ladder_summary.json" \
  --out "$OUT_DIR/advisor.json" \
  --report-out "$OUT_DIR/advisor.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_failure_policy_patch_advisor_demo")
payload = json.loads((out / "advisor.json").read_text(encoding="utf-8"))
advice = payload.get("advice") or {}
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
    "action_present": "PASS" if isinstance(advice.get("suggested_action"), str) else "FAIL",
    "confidence_present": "PASS" if isinstance(advice.get("confidence"), (int, float)) else "FAIL",
    "threshold_patch_present": "PASS" if isinstance(advice.get("threshold_patch"), dict) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "advisor_status": payload.get("status"),
    "suggested_action": advice.get("suggested_action"),
    "suggested_policy_profile": advice.get("suggested_policy_profile"),
    "confidence": advice.get("confidence"),
    "reason_count": len(advice.get("reasons") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Failure Policy Patch Advisor Demo",
            "",
            f"- advisor_status: `{summary['advisor_status']}`",
            f"- suggested_action: `{summary['suggested_action']}`",
            f"- suggested_policy_profile: `{summary['suggested_policy_profile']}`",
            f"- confidence: `{summary['confidence']}`",
            f"- reason_count: `{summary['reason_count']}`",
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
print(json.dumps({"bundle_status": bundle_status, "advisor_status": summary["advisor_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
