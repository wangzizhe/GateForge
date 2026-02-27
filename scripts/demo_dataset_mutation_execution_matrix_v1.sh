#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_mutation_execution_matrix_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/real_model_registry.json" <<'JSON'
{
  "schema_version": "real_model_intake_registry_rows_v1",
  "models": [
    {"model_id": "mdl_medium_1", "suggested_scale": "medium"},
    {"model_id": "mdl_large_1", "suggested_scale": "large"}
  ]
}
JSON

cat > "$OUT_DIR/validated_mutation_manifest.json" <<'JSON'
{
  "schema_version": "validated_mutation_manifest_v1",
  "mutations": [
    {"mutation_id": "mut_001", "target_model_id": "mdl_medium_1", "expected_failure_type": "simulate_error"},
    {"mutation_id": "mut_002", "target_model_id": "mdl_medium_1", "expected_failure_type": "model_check_error"},
    {"mutation_id": "mut_003", "target_model_id": "mdl_large_1", "expected_failure_type": "simulate_error"},
    {"mutation_id": "mut_004", "target_model_id": "mdl_large_1", "expected_failure_type": "semantic_regression"}
  ]
}
JSON

cat > "$OUT_DIR/replay_observations.json" <<'JSON'
{
  "observations": [
    {"mutation_id": "mut_001", "observed_failure_types": ["simulate_error", "simulate_error"]},
    {"mutation_id": "mut_002", "observed_failure_types": ["model_check_error", "model_check_error"]},
    {"mutation_id": "mut_003", "observed_failure_types": ["simulate_error", "simulate_error"]},
    {"mutation_id": "mut_004", "observed_failure_types": ["semantic_regression", "semantic_regression"]}
  ]
}
JSON

python3 -m gateforge.dataset_mutation_execution_matrix_v1 \
  --real-model-registry "$OUT_DIR/real_model_registry.json" \
  --validated-mutation-manifest "$OUT_DIR/validated_mutation_manifest.json" \
  --replay-observations "$OUT_DIR/replay_observations.json" \
  --matrix-out "$OUT_DIR/matrix.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_mutation_execution_matrix_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
matrix = json.loads((out / "matrix.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "matrix_cells_present": "PASS" if int(summary.get("matrix_cell_count", 0) or 0) >= 1 else "FAIL",
    "matrix_schema_present": "PASS" if matrix.get("schema_version") == "mutation_execution_matrix_v1" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "matrix_status": summary.get("status"),
    "matrix_cell_count": summary.get("matrix_cell_count"),
    "matrix_execution_ratio_pct": summary.get("matrix_execution_ratio_pct"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "matrix_status": payload["matrix_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
