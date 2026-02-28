#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_mutation_coverage_matrix_v2_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/registry.json" <<'JSON'
{
  "models": [
    {"model_id": "mdl_m_1", "suggested_scale": "medium"},
    {"model_id": "mdl_l_1", "suggested_scale": "large"}
  ]
}
JSON

cat > "$OUT_DIR/manifest.json" <<'JSON'
{
  "mutations": [
    {"mutation_id": "mut_1", "target_model_id": "mdl_m_1", "expected_failure_type": "simulate_error", "mutation_type": "param_shift"},
    {"mutation_id": "mut_2", "target_model_id": "mdl_l_1", "expected_failure_type": "solver_non_convergence", "mutation_type": "equation_flip"},
    {"mutation_id": "mut_3", "target_model_id": "mdl_l_1", "expected_failure_type": "semantic_regression", "mutation_type": "boundary_swap"}
  ]
}
JSON

cat > "$OUT_DIR/observations.json" <<'JSON'
{
  "observations": [
    {"mutation_id": "mut_1", "observed_failure_types": ["simulate_error"]},
    {"mutation_id": "mut_2", "observed_failure_types": ["solver_non_convergence"]}
  ]
}
JSON

python3 -m gateforge.dataset_mutation_coverage_matrix_v2 \
  --real-model-registry "$OUT_DIR/registry.json" \
  --validated-mutation-manifest "$OUT_DIR/manifest.json" \
  --replay-observations "$OUT_DIR/observations.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_mutation_coverage_matrix_v2_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("matrix_coverage_score"), (int, float)) else "FAIL",
    "cells_present": "PASS" if isinstance(summary.get("total_matrix_cells"), int) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "matrix_status": summary.get("status"),
    "matrix_coverage_score": summary.get("matrix_coverage_score"),
    "total_matrix_cells": summary.get("total_matrix_cells"),
    "high_risk_uncovered_cells": summary.get("high_risk_uncovered_cells"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "matrix_status": payload["matrix_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
