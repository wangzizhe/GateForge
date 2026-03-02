#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_execution_cadence_history_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

cat > "$OUT_DIR/c1.json" <<'JSON'
{"status":"PASS","execution_cadence_score":78.0,"weekly_model_target":3,"weekly_mutation_target":10}
JSON

cat > "$OUT_DIR/c2.json" <<'JSON'
{"status":"NEEDS_REVIEW","execution_cadence_score":70.0,"weekly_model_target":2,"weekly_mutation_target":11}
JSON

python3 -m gateforge.dataset_moat_execution_cadence_history_v1 \
  --moat-execution-cadence-summary "$OUT_DIR/c1.json" \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/s1.json" \
  --report-out "$OUT_DIR/s1.md"

python3 -m gateforge.dataset_moat_execution_cadence_history_v1 \
  --moat-execution-cadence-summary "$OUT_DIR/c2.json" \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_moat_execution_cadence_history_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "records_at_least_two": "PASS" if int(summary.get("total_records", 0)) >= 2 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "history_status": summary.get("status"),
    "avg_execution_cadence_score": summary.get("avg_execution_cadence_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "history_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
