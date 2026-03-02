#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_weekly_summary_history_trend_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/previous.json" <<'JSON'
{"status":"PASS","avg_real_model_count":10.0,"avg_stability_score":88.0,"avg_advantage_score":8.0}
JSON
cat > "$OUT_DIR/current.json" <<'JSON'
{"status":"PASS","avg_real_model_count":12.0,"avg_stability_score":90.0,"avg_advantage_score":10.0}
JSON

python3 -m gateforge.dataset_moat_weekly_summary_history_trend_v1 \
  --previous "$OUT_DIR/previous.json" \
  --current "$OUT_DIR/current.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_moat_weekly_summary_history_trend_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
trend = summary.get("trend") if isinstance(summary.get("trend"), dict) else {}
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "transition_present": "PASS" if isinstance(trend.get("status_transition"), str) and "->" in trend.get("status_transition") else "FAIL",
    "delta_present": "PASS" if isinstance(trend.get("delta_avg_stability_score"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "trend_status": summary.get("status"),
    "status_transition": trend.get("status_transition"),
    "delta_avg_stability_score": trend.get("delta_avg_stability_score"),
    "delta_avg_advantage_score": trend.get("delta_avg_advantage_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "trend_status": payload["trend_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
