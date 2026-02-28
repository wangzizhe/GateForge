#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_supply_pipeline_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/intake_summary.json" <<'JSON'
{"status":"PASS","accepted_count":5,"accepted_large_count":2,"reject_rate_pct":18.0}
JSON
cat > "$OUT_DIR/backlog_summary.json" <<'JSON'
{"status":"PASS","backlog_item_count":3,"p0_count":0}
JSON
cat > "$OUT_DIR/license_summary.json" <<'JSON'
{"status":"PASS","disallowed_license_count":0,"unknown_license_ratio_pct":0.0}
JSON
cat > "$OUT_DIR/growth_summary.json" <<'JSON'
{"status":"PASS","delta_total_real_models":2,"delta_large_models":1,"growth_velocity_score":82.0}
JSON

python3 -m gateforge.dataset_real_model_supply_pipeline_v1 \
  --real-model-intake-summary "$OUT_DIR/intake_summary.json" \
  --real-model-intake-backlog-summary "$OUT_DIR/backlog_summary.json" \
  --real-model-license-compliance-summary "$OUT_DIR/license_summary.json" \
  --real-model-growth-trend-summary "$OUT_DIR/growth_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_real_model_supply_pipeline_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("supply_pipeline_score"), (int, float)) else "FAIL",
    "new_models_present": "PASS" if isinstance(summary.get("new_models_30d"), int) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "supply_pipeline_status": summary.get("status"),
    "supply_pipeline_score": summary.get("supply_pipeline_score"),
    "new_models_30d": summary.get("new_models_30d"),
    "large_model_candidates_30d": summary.get("large_model_candidates_30d"),
    "license_blockers": summary.get("license_blockers"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "supply_pipeline_status": payload["supply_pipeline_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
