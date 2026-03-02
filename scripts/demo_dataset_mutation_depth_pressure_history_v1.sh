#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_mutation_depth_pressure_history_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

cat > "$OUT_DIR/board_1.json" <<'JSON'
{"status":"PASS","mutation_depth_pressure_index":28.0,"high_risk_gap_count":0,"missing_recipe_count":0,"recommended_weekly_mutation_target":6}
JSON

cat > "$OUT_DIR/board_2.json" <<'JSON'
{"status":"NEEDS_REVIEW","mutation_depth_pressure_index":39.0,"high_risk_gap_count":1,"missing_recipe_count":2,"recommended_weekly_mutation_target":10}
JSON

python3 -m gateforge.dataset_mutation_depth_pressure_history_v1 \
  --mutation-depth-pressure-board-summary "$OUT_DIR/board_1.json" \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/summary_1.json" \
  --report-out "$OUT_DIR/summary_1.md"

python3 -m gateforge.dataset_mutation_depth_pressure_history_v1 \
  --mutation-depth-pressure-board-summary "$OUT_DIR/board_2.json" \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_mutation_depth_pressure_history_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "records_present": "PASS" if int(summary.get("total_records", 0)) >= 2 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "history_status": summary.get("status"),
    "total_records": summary.get("total_records"),
    "avg_pressure_index": summary.get("avg_pressure_index"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "history_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
