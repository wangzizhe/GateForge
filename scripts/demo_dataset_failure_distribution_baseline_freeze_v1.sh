#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_distribution_baseline_freeze_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/moat_scorecard_baseline_summary.json" <<'JSON'
{"scorecard_status":"PASS","baseline_id":"moat-baseline-4097cb0d1533","failure_distribution_stability_score":90.0}
JSON
cat > "$OUT_DIR/failure_distribution_benchmark_summary.json" <<'JSON'
{"benchmark_v2_status":"PASS","total_cases_after":9,"failure_type_drift":0.03,"model_scale_drift":0.04}
JSON
cat > "$OUT_DIR/failure_distribution_quality_gate_summary.json" <<'JSON'
{"quality_gate_status":"PASS","gate_result":"PASS","unique_failure_types":6}
JSON

python3 -m gateforge.dataset_failure_distribution_baseline_freeze_v1 \
  --moat-scorecard-baseline-summary "$OUT_DIR/moat_scorecard_baseline_summary.json" \
  --failure-distribution-benchmark-summary "$OUT_DIR/failure_distribution_benchmark_summary.json" \
  --failure-distribution-quality-gate-summary "$OUT_DIR/failure_distribution_quality_gate_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_failure_distribution_baseline_freeze_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
locked = summary.get("locked_metrics") if isinstance(summary.get("locked_metrics"), dict) else {}
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "freeze_id_present": "PASS" if isinstance(summary.get("freeze_id"), str) and summary.get("freeze_id") else "FAIL",
    "locked_metrics_present": "PASS" if isinstance(locked.get("total_cases_after"), int) and isinstance(locked.get("failure_type_drift"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "freeze_status": summary.get("status"),
    "freeze_id": summary.get("freeze_id"),
    "baseline_id": summary.get("baseline_id"),
    "failure_distribution_stability_score": locked.get("failure_distribution_stability_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "freeze_status": payload["freeze_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
