#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_anchor_brief_history_trend_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/previous.json" <<'JSON'
{"status":"PASS","latest_recommendation":"PUBLISH","avg_anchor_brief_score":84.0,"publish_rate":1.0}
JSON
cat > "$OUT_DIR/current.json" <<'JSON'
{"status":"NEEDS_REVIEW","latest_recommendation":"PUBLISH_WITH_GUARDS","avg_anchor_brief_score":74.0,"publish_rate":0.5}
JSON

python3 -m gateforge.dataset_moat_anchor_brief_history_trend_v1 \
  --current "$OUT_DIR/current.json" \
  --previous "$OUT_DIR/previous.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_moat_anchor_brief_history_trend_v1_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
trend = payload.get("trend") or {}
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "transition_present": "PASS" if isinstance(trend.get("status_transition"), str) and "->" in str(trend.get("status_transition")) else "FAIL",
    "alerts_present": "PASS" if isinstance(trend.get("alerts"), list) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "trend_status": payload.get("status"),
    "status_transition": trend.get("status_transition"),
    "recommendation_transition": trend.get("recommendation_transition"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "trend_status": demo["trend_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
