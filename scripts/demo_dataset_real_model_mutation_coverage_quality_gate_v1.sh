#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_mutation_coverage_quality_gate_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/registry.json" <<'JSON'
{
  "models": [
    {"model_id":"m_med","suggested_scale":"medium"},
    {"model_id":"m_lrg","suggested_scale":"large"}
  ]
}
JSON

cat > "$OUT_DIR/manifest.json" <<'JSON'
{
  "mutations": [
    {"mutation_id":"a1","target_model_id":"m_med","expected_failure_type":"simulate_error"},
    {"mutation_id":"a2","target_model_id":"m_med","expected_failure_type":"model_check_error"},
    {"mutation_id":"a3","target_model_id":"m_med","expected_failure_type":"semantic_regression"},
    {"mutation_id":"a4","target_model_id":"m_med","expected_failure_type":"numerical_instability"},
    {"mutation_id":"a5","target_model_id":"m_med","expected_failure_type":"constraint_violation"},
    {"mutation_id":"b1","target_model_id":"m_lrg","expected_failure_type":"simulate_error"},
    {"mutation_id":"b2","target_model_id":"m_lrg","expected_failure_type":"model_check_error"},
    {"mutation_id":"b3","target_model_id":"m_lrg","expected_failure_type":"semantic_regression"},
    {"mutation_id":"b4","target_model_id":"m_lrg","expected_failure_type":"numerical_instability"},
    {"mutation_id":"b5","target_model_id":"m_lrg","expected_failure_type":"constraint_violation"}
  ]
}
JSON

cat > "$OUT_DIR/raw_obs.json" <<'JSON'
{
  "observations": [
    {"mutation_id":"a1","execution_status":"EXECUTED"},
    {"mutation_id":"a2","execution_status":"EXECUTED"},
    {"mutation_id":"a3","execution_status":"EXECUTED"},
    {"mutation_id":"a4","execution_status":"EXECUTED"},
    {"mutation_id":"a5","execution_status":"EXECUTED"},
    {"mutation_id":"b1","execution_status":"EXECUTED"},
    {"mutation_id":"b2","execution_status":"EXECUTED"},
    {"mutation_id":"b3","execution_status":"EXECUTED"},
    {"mutation_id":"b4","execution_status":"EXECUTED"},
    {"mutation_id":"b5","execution_status":"EXECUTED"}
  ]
}
JSON

python3 -m gateforge.dataset_real_model_mutation_coverage_quality_gate_v1 \
  --real-model-registry "$OUT_DIR/registry.json" \
  --validated-mutation-manifest "$OUT_DIR/manifest.json" \
  --mutation-raw-observations "$OUT_DIR/raw_obs.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_real_model_mutation_coverage_quality_gate_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "required_cells_full": "PASS" if int(summary.get("required_cell_count", 0) or 0) == int(summary.get("covered_required_cell_count", -1) or -1) else "FAIL",
    "matrix_cells_present": "PASS" if int(summary.get("matrix_cell_count", 0) or 0) >= 10 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "bundle_status": bundle_status,
    "status": summary.get("status"),
    "required_cell_coverage_ratio_pct": summary.get("required_cell_coverage_ratio_pct"),
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "status": payload["status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
