#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_corpus_saturation_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/failure_corpus_db.json" <<'JSON'
{
  "schema_version": "failure_corpus_db_v1",
  "cases": [
    {"case_id":"c1","failure_type":"simulate_error","model_scale":"small"},
    {"case_id":"c2","failure_type":"simulate_error","model_scale":"large"},
    {"case_id":"c3","failure_type":"model_check_error","model_scale":"medium"},
    {"case_id":"c4","failure_type":"semantic_regression","model_scale":"large"}
  ]
}
JSON

cat > "$OUT_DIR/failure_baseline_pack.json" <<'JSON'
{
  "selected_cases": [
    {"failure_type":"simulate_error"},
    {"failure_type":"model_check_error"},
    {"failure_type":"semantic_regression"},
    {"failure_type":"numerical_instability"}
  ]
}
JSON

python3 -m gateforge.dataset_failure_corpus_saturation_v1 \
  --failure-corpus-db "$OUT_DIR/failure_corpus_db.json" \
  --failure-baseline-pack "$OUT_DIR/failure_baseline_pack.json" \
  --target-min-per-failure-type 3 \
  --target-min-large-per-failure-type 1 \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_failure_corpus_saturation_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "saturation_present": "PASS" if summary.get("saturation_index") is not None else "FAIL",
    "gaps_field_present": "PASS" if summary.get("total_gap_actions") is not None else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "saturation_status": summary.get("status"),
    "saturation_index": summary.get("saturation_index"),
    "total_gap_actions": summary.get("total_gap_actions"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "saturation_status": payload["saturation_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
