#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_mutation_coverage_depth_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/registry.json" <<'JSON'
{
  "schema_version": "real_model_intake_registry_rows_v1",
  "models": [
    {"model_id": "mdl_medium_1", "suggested_scale": "medium"},
    {"model_id": "mdl_large_1", "suggested_scale": "large"}
  ]
}
JSON

cat > "$OUT_DIR/manifest.json" <<'JSON'
{
  "schema_version": "validated_mutation_manifest_v1",
  "mutations": [
    {"mutation_id": "mut_001", "target_model_id": "mdl_medium_1", "expected_failure_type": "simulate_error", "expected_stage": "simulate"},
    {"mutation_id": "mut_002", "target_model_id": "mdl_medium_1", "expected_failure_type": "model_check_error", "expected_stage": "compile"},
    {"mutation_id": "mut_003", "target_model_id": "mdl_large_1", "expected_failure_type": "semantic_regression", "expected_stage": "simulate"},
    {"mutation_id": "mut_004", "target_model_id": "mdl_large_1", "expected_failure_type": "solver_non_convergence", "expected_stage": "simulate"}
  ]
}
JSON

cat > "$OUT_DIR/observations.json" <<'JSON'
{
  "observations": [
    {"mutation_id": "mut_001", "observed_failure_types": ["simulate_error", "simulate_error"]},
    {"mutation_id": "mut_002", "observed_failure_types": ["model_check_error", "model_check_error"]},
    {"mutation_id": "mut_003", "observed_failure_types": ["semantic_regression"]}
  ]
}
JSON

python3 -m gateforge.dataset_mutation_coverage_depth_v1 \
  --real-model-registry "$OUT_DIR/registry.json" \
  --validated-mutation-manifest "$OUT_DIR/manifest.json" \
  --replay-observations "$OUT_DIR/observations.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_mutation_coverage_depth_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("coverage_depth_score"), (int, float)) else "FAIL",
    "cells_present": "PASS" if isinstance(summary.get("total_cells"), int) and int(summary.get("total_cells")) >= 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "coverage_status": summary.get("status"),
    "coverage_depth_score": summary.get("coverage_depth_score"),
    "uncovered_cells_count": summary.get("uncovered_cells_count"),
    "high_risk_gaps_count": summary.get("high_risk_gaps_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "coverage_status": payload["coverage_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
