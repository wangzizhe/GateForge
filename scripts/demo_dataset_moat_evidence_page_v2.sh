#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_evidence_page_v2_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/anchor.json" <<'JSON'
{"status":"PASS","anchor_brief_score":82.0}
JSON
cat > "$OUT_DIR/growth.json" <<'JSON'
{"status":"PASS","growth_velocity_score":81.0}
JSON
cat > "$OUT_DIR/supply.json" <<'JSON'
{"status":"PASS","supply_pipeline_score":84.0,"new_models_30d":2,"large_model_candidates_30d":1}
JSON
cat > "$OUT_DIR/matrix.json" <<'JSON'
{"status":"PASS","matrix_coverage_score":83.0}
JSON
cat > "$OUT_DIR/stability_history.json" <<'JSON'
{"status":"PASS","avg_stability_score":80.0}
JSON
cat > "$OUT_DIR/stability_history_trend.json" <<'JSON'
{"status":"PASS","trend":{"status_transition":"PASS->PASS"}}
JSON
cat > "$OUT_DIR/moat_trend_snapshot.json" <<'JSON'
{"metrics":{"target_gap_pressure_index":76.5,"model_asset_target_gap_score":28.5}}
JSON

python3 -m gateforge.dataset_moat_evidence_page_v2 \
  --moat-anchor-brief-summary "$OUT_DIR/anchor.json" \
  --real-model-growth-trend-summary "$OUT_DIR/growth.json" \
  --real-model-supply-pipeline-summary "$OUT_DIR/supply.json" \
  --mutation-coverage-matrix-summary "$OUT_DIR/matrix.json" \
  --failure-distribution-stability-history-summary "$OUT_DIR/stability_history.json" \
  --failure-distribution-stability-history-trend-summary "$OUT_DIR/stability_history_trend.json" \
  --moat-trend-snapshot-summary "$OUT_DIR/moat_trend_snapshot.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_moat_evidence_page_v2_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("evidence_score"), (int, float)) else "FAIL",
    "claims_present": "PASS" if isinstance(summary.get("public_claims"), list) and len(summary.get("public_claims")) >= 5 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "evidence_status": summary.get("status"),
    "publishable": summary.get("publishable"),
    "evidence_score": summary.get("evidence_score"),
    "target_gap_pressure_index": summary.get("target_gap_pressure_index"),
    "model_asset_target_gap_score": summary.get("model_asset_target_gap_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "evidence_status": payload["evidence_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
