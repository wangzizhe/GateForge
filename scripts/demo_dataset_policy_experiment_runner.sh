#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_policy_experiment_runner_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/policy_patch_replay_evaluator.json" <<'JSON'
{
  "status": "PASS",
  "evaluation_score": 6,
  "delta": {
    "detection_rate": 0.04,
    "false_positive_rate": -0.01,
    "regression_rate": -0.02,
    "review_load": -1
  }
}
JSON

cat > "$OUT_DIR/replay_quality_guard.json" <<'JSON'
{
  "status": "PASS",
  "confidence_level": "high",
  "delta_magnitude_score": 0.08
}
JSON

cat > "$OUT_DIR/failure_policy_patch_advisor.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "advice": {
    "suggested_action": "tighten"
  }
}
JSON

cat > "$OUT_DIR/moat_trend_snapshot.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "metrics": {
    "moat_score": 67.5
  }
}
JSON

python3 -m gateforge.dataset_policy_experiment_runner \
  --policy-patch-replay-evaluator "$OUT_DIR/policy_patch_replay_evaluator.json" \
  --replay-quality-guard "$OUT_DIR/replay_quality_guard.json" \
  --failure-policy-patch-advisor "$OUT_DIR/failure_policy_patch_advisor.json" \
  --moat-trend-snapshot "$OUT_DIR/moat_trend_snapshot.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_policy_experiment_runner_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
experiments = payload.get("experiments") if isinstance(payload.get("experiments"), list) else []
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "experiments_present": "PASS" if len(experiments) >= 3 else "FAIL",
    "recommendation_present": "PASS" if isinstance(payload.get("recommendation"), str) and payload.get("recommendation") else "FAIL",
    "recommended_id_present": "PASS" if isinstance(payload.get("recommended_experiment_id"), str) and payload.get("recommended_experiment_id") else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "runner_status": payload.get("status"),
    "recommendation": payload.get("recommendation"),
    "recommended_experiment_id": payload.get("recommended_experiment_id"),
    "top_score": (experiments[0] if experiments else {}).get("experiment_score"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Policy Experiment Runner Demo",
            "",
            f"- runner_status: `{summary['runner_status']}`",
            f"- recommendation: `{summary['recommendation']}`",
            f"- recommended_experiment_id: `{summary['recommended_experiment_id']}`",
            f"- top_score: `{summary['top_score']}`",
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
print(json.dumps({"bundle_status": bundle_status, "runner_status": summary["runner_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
