#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_model_asset_target_gap_history_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

cat > "$OUT_DIR/r1.json" <<'JSON'
{"status":"NEEDS_REVIEW","target_gap_score":28.5,"critical_gap_count":1}
JSON
cat > "$OUT_DIR/r2.json" <<'JSON'
{"status":"PASS","target_gap_score":20.0,"critical_gap_count":0}
JSON

python3 -m gateforge.dataset_model_asset_target_gap_history_v1 \
  --record "$OUT_DIR/r1.json" \
  --record "$OUT_DIR/r2.json" \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_model_asset_target_gap_history_v1_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "total_records_present": "PASS" if isinstance(payload.get("total_records"), int) else "FAIL",
    "avg_target_gap_score_present": "PASS" if isinstance(payload.get("avg_target_gap_score"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "history_status": payload.get("status"),
    "total_records": payload.get("total_records"),
    "avg_target_gap_score": payload.get("avg_target_gap_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "history_status": demo["history_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
