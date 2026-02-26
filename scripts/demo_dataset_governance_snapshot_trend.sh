#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_governance_snapshot_trend_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/previous_summary.json" <<'JSON'
{
  "status": "PASS",
  "risks": ["dataset_history_trend_needs_review"],
  "kpis": {
    "dataset_pipeline_deduplicated_cases": 8,
    "dataset_pipeline_failure_case_rate": 0.2,
    "dataset_governance_total_records": 4,
    "dataset_governance_trend_alert_count": 0,
    "dataset_failure_taxonomy_coverage_status": "PASS",
    "dataset_failure_taxonomy_total_cases": 4,
    "dataset_failure_taxonomy_unique_failure_types": 2,
    "dataset_failure_taxonomy_missing_failure_types_count": 3,
    "dataset_failure_taxonomy_missing_model_scales_count": 1,
    "dataset_promotion_effectiveness_history_trend_status": "PASS",
    "dataset_promotion_effectiveness_history_latest_decision": "KEEP"
  }
}
JSON

bash scripts/demo_dataset_governance_snapshot.sh

python3 -m gateforge.dataset_governance_snapshot_trend \
  --summary artifacts/dataset_governance_snapshot_demo/summary.json \
  --previous-summary "$OUT_DIR/previous_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_governance_snapshot_trend_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
trend = payload.get("trend", {})
flags = {
    "has_status_transition": "PASS" if isinstance(trend.get("status_transition"), str) and "->" in trend.get("status_transition", "") else "FAIL",
    "has_kpi_delta": "PASS" if isinstance(trend.get("kpi_delta"), dict) else "FAIL",
    "has_status_delta": "PASS" if isinstance(trend.get("status_delta"), dict) else "FAIL",
    "has_severity_fields": "PASS" if isinstance(trend.get("severity_score"), int) and trend.get("severity_level") in {"low", "medium", "high"} else "FAIL",
    "has_new_risks_list": "PASS" if isinstance(trend.get("new_risks"), list) else "FAIL",
    "has_resolved_risks_list": "PASS" if isinstance(trend.get("resolved_risks"), list) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "status": payload.get("status"),
    "status_transition": trend.get("status_transition"),
    "severity_score": trend.get("severity_score"),
    "severity_level": trend.get("severity_level"),
    "new_risks_count": len(trend.get("new_risks", [])) if isinstance(trend.get("new_risks"), list) else 0,
    "resolved_risks_count": len(trend.get("resolved_risks", [])) if isinstance(trend.get("resolved_risks"), list) else 0,
    "promotion_effectiveness_history_trend_transition": (trend.get("status_delta") or {}).get(
        "dataset_promotion_effectiveness_history_trend_status_transition"
    ),
    "failure_taxonomy_coverage_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_failure_taxonomy_coverage_status_transition"
    ),
    "status_delta_alert_count": len((trend.get("status_delta") or {}).get("alerts") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Governance Snapshot Trend Demo",
            "",
            f"- status: `{demo['status']}`",
            f"- status_transition: `{demo['status_transition']}`",
            f"- severity_score: `{demo['severity_score']}`",
            f"- severity_level: `{demo['severity_level']}`",
            f"- new_risks_count: `{demo['new_risks_count']}`",
            f"- resolved_risks_count: `{demo['resolved_risks_count']}`",
            f"- promotion_effectiveness_history_trend_transition: `{demo['promotion_effectiveness_history_trend_transition']}`",
            f"- failure_taxonomy_coverage_status_transition: `{demo['failure_taxonomy_coverage_status_transition']}`",
            f"- status_delta_alert_count: `{demo['status_delta_alert_count']}`",
            f"- bundle_status: `{demo['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
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
