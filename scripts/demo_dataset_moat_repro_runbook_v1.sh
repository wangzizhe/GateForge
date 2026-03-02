#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_repro_runbook_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/moat_scorecard_baseline_summary.json" <<'JSON'
{
  "status":"PASS",
  "baseline_id":"moat-baseline-4097cb0d1533",
  "indicators":{
    "real_model_count":4,
    "reproducible_mutation_count":12,
    "failure_distribution_stability_score":90.0
  }
}
JSON
cat > "$OUT_DIR/model_asset_inventory_report_summary.json" <<'JSON'
{"status":"PASS","total_models":8}
JSON
cat > "$OUT_DIR/failure_distribution_baseline_freeze_summary.json" <<'JSON'
{"status":"PASS","freeze_id":"failure-freeze-abc123def456","locked_metrics":{"failure_distribution_stability_score":90.0}}
JSON
cat > "$OUT_DIR/gateforge_vs_plain_ci_benchmark_summary.json" <<'JSON'
{"comparison_status":"PASS","advantage_score":10}
JSON

python3 -m gateforge.dataset_moat_repro_runbook_v1 \
  --moat-scorecard-baseline-summary "$OUT_DIR/moat_scorecard_baseline_summary.json" \
  --model-asset-inventory-report-summary "$OUT_DIR/model_asset_inventory_report_summary.json" \
  --failure-distribution-baseline-freeze-summary "$OUT_DIR/failure_distribution_baseline_freeze_summary.json" \
  --gateforge-vs-plain-ci-benchmark-summary "$OUT_DIR/gateforge_vs_plain_ci_benchmark_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_moat_repro_runbook_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "readiness_present": "PASS" if summary.get("readiness") in {"READY", "NEEDS_EVIDENCE", "BLOCKED"} else "FAIL",
    "steps_present": "PASS" if isinstance(summary.get("repro_steps"), list) and len(summary.get("repro_steps")) >= 3 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "runbook_status": summary.get("status"),
    "readiness": summary.get("readiness"),
    "expected_signals": summary.get("expected_signals"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "runbook_status": payload["runbook_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
