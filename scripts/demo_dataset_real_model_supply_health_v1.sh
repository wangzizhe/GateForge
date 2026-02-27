#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_supply_health_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/intake_summary.json" <<'JSON'
{
  "status":"PASS",
  "accepted_count":4,
  "accepted_large_count":1,
  "accepted_scale_counts":{"small":1,"medium":2,"large":1},
  "reject_rate_pct":22.5,
  "weekly_target_status":"PASS"
}
JSON
cat > "$OUT_DIR/license_summary.json" <<'JSON'
{"status":"PASS","license_risk_score":8.0}
JSON
cat > "$OUT_DIR/backlog_summary.json" <<'JSON'
{"status":"PASS","p0_count":0}
JSON
cat > "$OUT_DIR/yield_summary.json" <<'JSON'
{"status":"PASS","effective_yield_score":82.0}
JSON

python3 -m gateforge.dataset_real_model_supply_health_v1 \
  --real-model-intake-summary "$OUT_DIR/intake_summary.json" \
  --real-model-license-compliance-summary "$OUT_DIR/license_summary.json" \
  --real-model-intake-backlog-summary "$OUT_DIR/backlog_summary.json" \
  --real-model-failure-yield-summary "$OUT_DIR/yield_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_real_model_supply_health_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if float(summary.get("supply_health_score", 0) or 0) >= 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({"supply_health_status": summary.get("status"), "supply_health_score": summary.get("supply_health_score"), "bundle_status": bundle_status, "result_flags": flags}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "supply_health_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
