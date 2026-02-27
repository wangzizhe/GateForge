#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_failure_yield_tracker_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/intake_ledger.json" <<'JSON'
{
  "records": [
    {"model_id": "m1", "decision": "ACCEPT"},
    {"model_id": "m2", "decision": "ACCEPT"},
    {"model_id": "m3", "decision": "REJECT"}
  ]
}
JSON

cat > "$OUT_DIR/matrix_summary.json" <<'JSON'
{
  "executed_mutations": 5,
  "total_mutations": 6,
  "matrix_execution_ratio_pct": 83.33
}
JSON

python3 -m gateforge.dataset_real_model_failure_yield_tracker_v1 \
  --real-model-intake-ledger "$OUT_DIR/intake_ledger.json" \
  --mutation-execution-matrix-summary "$OUT_DIR/matrix_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_real_model_failure_yield_tracker_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "yield_present": "PASS" if float(summary.get("yield_per_accepted_model", 0) or 0) >= 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "yield_tracker_status": summary.get("status"),
    "effective_yield_score": summary.get("effective_yield_score"),
    "yield_band": summary.get("yield_band"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "yield_tracker_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
