#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_weekly_summary_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/moat_scorecard_baseline_summary.json" <<'JSON'
{
  "status":"PASS",
  "baseline_id":"moat-baseline-4097cb0d1533",
  "indicators":{
    "real_model_count":12,
    "reproducible_mutation_count":36,
    "failure_type_coverage_score":92.0,
    "failure_distribution_stability_score":90.0,
    "gateforge_vs_plain_ci_advantage_score":10
  }
}
JSON
cat > "$OUT_DIR/model_asset_inventory_report_summary.json" <<'JSON'
{"status":"PASS","total_models":12,"by_scale":{"small":6,"medium":4,"large":2}}
JSON
cat > "$OUT_DIR/failure_distribution_baseline_freeze_summary.json" <<'JSON'
{"status":"PASS","freeze_id":"failure-freeze-abc123def456","locked_metrics":{"failure_distribution_stability_score":90.0}}
JSON
cat > "$OUT_DIR/moat_repro_runbook_summary.json" <<'JSON'
{"status":"PASS","readiness":"READY","expected_signals":{"real_model_count":12,"reproducible_mutation_count":36}}
JSON

python3 -m gateforge.dataset_moat_weekly_summary_v1 \
  --week-tag "2026-W10" \
  --moat-scorecard-baseline-summary "$OUT_DIR/moat_scorecard_baseline_summary.json" \
  --model-asset-inventory-report-summary "$OUT_DIR/model_asset_inventory_report_summary.json" \
  --failure-distribution-baseline-freeze-summary "$OUT_DIR/failure_distribution_baseline_freeze_summary.json" \
  --moat-repro-runbook-summary "$OUT_DIR/moat_repro_runbook_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_moat_weekly_summary_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "week_tag_present": "PASS" if isinstance(summary.get("week_tag"), str) and summary.get("week_tag") else "FAIL",
    "kpis_present": "PASS" if isinstance(summary.get("kpis"), dict) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "weekly_status": summary.get("status"),
    "week_tag": summary.get("week_tag"),
    "kpis": summary.get("kpis"),
    "focus_next_week": summary.get("focus_next_week"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "weekly_status": payload["weekly_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
