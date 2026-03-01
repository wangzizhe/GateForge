#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_model_intake_board_history_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

cat > "$OUT_DIR/r1.json" <<'JSON'
{"status":"PASS","board_score":82.0,"total_candidates":4,"blocked_count":1,"ready_count":2,"ingested_count":1}
JSON

cat > "$OUT_DIR/r2.json" <<'JSON'
{"status":"NEEDS_REVIEW","board_score":74.0,"total_candidates":4,"blocked_count":2,"ready_count":1,"ingested_count":1}
JSON

python3 -m gateforge.dataset_model_intake_board_history_v1 \
  --record "$OUT_DIR/r1.json" \
  --record "$OUT_DIR/r2.json" \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_model_intake_board_history_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "total_records_present": "PASS" if isinstance(summary.get("total_records"), int) else "FAIL",
    "avg_board_score_present": "PASS" if isinstance(summary.get("avg_board_score"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "history_status": summary.get("status"),
    "total_records": summary.get("total_records"),
    "avg_board_score": summary.get("avg_board_score"),
    "blocked_rate": summary.get("blocked_rate"),
    "ingested_rate": summary.get("ingested_rate"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "history_status": demo["history_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
