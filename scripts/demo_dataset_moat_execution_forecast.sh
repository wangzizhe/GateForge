#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_execution_forecast_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/modelica_failure_pack_planner.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "total_target_new_cases": 16,
  "medium_target_new_cases": 6,
  "large_target_new_cases": 4
}
JSON

cat > "$OUT_DIR/policy_experiment_runner.json" <<'JSON'
{
  "status": "PASS",
  "recommended_experiment_id": "policy_exp.balanced",
  "experiments": [
    {
      "experiment_id": "policy_exp.balanced",
      "experiment_score": 72.5,
      "risk_score": 37.0
    },
    {
      "experiment_id": "policy_exp.conservative",
      "experiment_score": 67.1,
      "risk_score": 28.0
    },
    {
      "experiment_id": "policy_exp.aggressive",
      "experiment_score": 64.3,
      "risk_score": 53.0
    }
  ]
}
JSON

cat > "$OUT_DIR/moat_trend_snapshot.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "metrics": {
    "moat_score": 61.4
  }
}
JSON

cat > "$OUT_DIR/replay_quality_guard.json" <<'JSON'
{
  "status": "PASS",
  "confidence_level": "high"
}
JSON

python3 -m gateforge.dataset_moat_execution_forecast \
  --modelica-failure-pack-planner "$OUT_DIR/modelica_failure_pack_planner.json" \
  --policy-experiment-runner "$OUT_DIR/policy_experiment_runner.json" \
  --moat-trend-snapshot "$OUT_DIR/moat_trend_snapshot.json" \
  --replay-quality-guard "$OUT_DIR/replay_quality_guard.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_moat_execution_forecast_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
forecast = payload.get("forecast") if isinstance(payload.get("forecast"), list) else []
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "forecast_present": "PASS" if len(forecast) == 3 else "FAIL",
    "preferred_scenario_present": "PASS" if payload.get("preferred_scenario") in {"cautious", "base", "stretch", "none"} else "FAIL",
    "projected_score_present": "PASS" if isinstance(payload.get("projected_moat_score_30d"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "forecast_status": payload.get("status"),
    "recommendation": payload.get("recommendation"),
    "preferred_scenario": payload.get("preferred_scenario"),
    "projected_moat_score_30d": payload.get("projected_moat_score_30d"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Moat Execution Forecast Demo",
            "",
            f"- forecast_status: `{summary['forecast_status']}`",
            f"- recommendation: `{summary['recommendation']}`",
            f"- preferred_scenario: `{summary['preferred_scenario']}`",
            f"- projected_moat_score_30d: `{summary['projected_moat_score_30d']}`",
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
print(json.dumps({"bundle_status": bundle_status, "forecast_status": summary["forecast_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
