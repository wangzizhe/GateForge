#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_model_asset_momentum_history_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

cat > "$OUT_DIR/r1.json" <<'JSON'
{"status":"PASS","momentum_score":82.0,"delta_total_real_models":2,"delta_large_models":1,"delta_mutation_coverage_depth_score":6.0,"delta_stability_score":3.0}
JSON
cat > "$OUT_DIR/r2.json" <<'JSON'
{"status":"PASS","momentum_score":79.0,"delta_total_real_models":1,"delta_large_models":1,"delta_mutation_coverage_depth_score":4.0,"delta_stability_score":2.0}
JSON

python3 -m gateforge.dataset_model_asset_momentum_history_v1 \
  --record "$OUT_DIR/r1.json" \
  --record "$OUT_DIR/r2.json" \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_model_asset_momentum_history_v1_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "total_records_present": "PASS" if isinstance(payload.get("total_records"), int) else "FAIL",
    "avg_momentum_score_present": "PASS" if isinstance(payload.get("avg_momentum_score"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "history_status": payload.get("status"),
    "total_records": payload.get("total_records"),
    "avg_momentum_score": payload.get("avg_momentum_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "history_status": demo["history_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
