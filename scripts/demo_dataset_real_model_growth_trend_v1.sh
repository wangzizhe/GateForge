#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_growth_trend_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/previous_portfolio.json" <<'JSON'
{"status":"PASS","total_real_models":3,"large_models":1,"active_domains_count":2,"portfolio_strength_score":72.0}
JSON
cat > "$OUT_DIR/current_portfolio.json" <<'JSON'
{"status":"PASS","total_real_models":5,"large_models":2,"active_domains_count":3,"portfolio_strength_score":84.0}
JSON

python3 -m gateforge.dataset_real_model_growth_trend_v1 \
  --current-portfolio-summary "$OUT_DIR/current_portfolio.json" \
  --previous-portfolio-summary "$OUT_DIR/previous_portfolio.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_real_model_growth_trend_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("growth_velocity_score"), (int, float)) else "FAIL",
    "delta_total_present": "PASS" if isinstance(summary.get("delta_total_real_models"), int) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "growth_trend_status": summary.get("status"),
    "growth_velocity_score": summary.get("growth_velocity_score"),
    "trend_band": summary.get("trend_band"),
    "delta_total_real_models": summary.get("delta_total_real_models"),
    "delta_large_models": summary.get("delta_large_models"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "growth_trend_status": payload["growth_trend_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
