#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_model_asset_target_gap_history_trend_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/previous.json" <<'JSON'
{"status":"PASS","avg_target_gap_score":20.0,"avg_critical_gap_count":0.0}
JSON

cat > "$OUT_DIR/current.json" <<'JSON'
{"status":"NEEDS_REVIEW","avg_target_gap_score":26.0,"avg_critical_gap_count":1.0}
JSON

python3 -m gateforge.dataset_model_asset_target_gap_history_trend_v1 \
  --current "$OUT_DIR/current.json" \
  --previous "$OUT_DIR/previous.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_model_asset_target_gap_history_trend_v1_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
trend = payload.get("trend") or {}
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "status_transition_present": "PASS" if isinstance(trend.get("status_transition"), str) and "->" in str(trend.get("status_transition")) else "FAIL",
    "alerts_present": "PASS" if isinstance(trend.get("alerts"), list) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "trend_status": payload.get("status"),
    "status_transition": trend.get("status_transition"),
    "delta_avg_target_gap_score": trend.get("delta_avg_target_gap_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "trend_status": demo["trend_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
