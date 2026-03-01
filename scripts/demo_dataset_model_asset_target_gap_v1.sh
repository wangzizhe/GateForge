#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_model_asset_target_gap_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/portfolio.json" <<'JSON'
{"status":"PASS","total_real_models":8,"large_models":2}
JSON
cat > "$OUT_DIR/momentum.json" <<'JSON'
{"status":"NEEDS_REVIEW","momentum_score":74.0,"delta_total_real_models":1,"delta_large_models":0}
JSON
cat > "$OUT_DIR/coverage.json" <<'JSON'
{"status":"PASS","coverage_depth_score":82.0}
JSON
cat > "$OUT_DIR/stability.json" <<'JSON'
{"status":"PASS","stability_score":79.0}
JSON

if [ "${GATEFORGE_DEMO_FAST:-0}" = "1" ]; then
  TARGET_TOTAL=10
  TARGET_LARGE=3
else
  TARGET_TOTAL=12
  TARGET_LARGE=4
fi

python3 -m gateforge.dataset_model_asset_target_gap_v1 \
  --real-model-intake-portfolio-summary "$OUT_DIR/portfolio.json" \
  --model-asset-momentum-summary "$OUT_DIR/momentum.json" \
  --mutation-coverage-depth-summary "$OUT_DIR/coverage.json" \
  --failure-distribution-stability-summary "$OUT_DIR/stability.json" \
  --target-total-real-models "$TARGET_TOTAL" \
  --target-large-models "$TARGET_LARGE" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md" || true

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_model_asset_target_gap_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("target_gap_score"), (int, float)) else "FAIL",
    "actions_present": "PASS" if isinstance(summary.get("top_actions"), list) and len(summary.get("top_actions") or []) > 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "target_gap_status": summary.get("status"),
    "target_gap_score": summary.get("target_gap_score"),
    "critical_gap_count": summary.get("critical_gap_count"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "target_gap_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
