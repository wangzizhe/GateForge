#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_defensibility_report_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/represent.json" <<'JSON'
{"status":"PASS","representativeness_score":78.0}
JSON

cat > "$OUT_DIR/unique.json" <<'JSON'
{"status":"PASS","asset_uniqueness_index":92.0}
JSON

cat > "$OUT_DIR/depth_hist.json" <<'JSON'
{"status":"NEEDS_REVIEW","avg_pressure_index":33.0}
JSON

cat > "$OUT_DIR/stability_trend.json" <<'JSON'
{"status":"PASS","trend":{"delta_avg_stability_score":1.0,"delta_avg_distribution_drift_score":-0.01}}
JSON

cat > "$OUT_DIR/plan.json" <<'JSON'
{"status":"PASS","execution_focus_score":74.0}
JSON

cat > "$OUT_DIR/weekly.json" <<'JSON'
{"status":"PASS"}
JSON

python3 -m gateforge.dataset_moat_defensibility_report_v1 \
  --modelica-representativeness-gate-summary "$OUT_DIR/represent.json" \
  --modelica-asset-uniqueness-index-summary "$OUT_DIR/unique.json" \
  --mutation-depth-pressure-history-summary "$OUT_DIR/depth_hist.json" \
  --failure-distribution-stability-history-trend-summary "$OUT_DIR/stability_trend.json" \
  --moat-hard-evidence-plan-summary "$OUT_DIR/plan.json" \
  --moat-weekly-summary "$OUT_DIR/weekly.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_moat_defensibility_report_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("moat_defensibility_score"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "defensibility_status": summary.get("status"),
    "moat_defensibility_score": summary.get("moat_defensibility_score"),
    "defensibility_band": summary.get("defensibility_band"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "defensibility_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
