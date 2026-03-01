#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_matrix_expansion_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/matrix_summary.json" <<'JSON'
{
  "status":"NEEDS_REVIEW",
  "matrix_coverage_score":78.0,
  "high_risk_uncovered_cells":2,
  "top_10_gap_plan":[
    {"model_scale":"large","failure_type":"solver_non_convergence","mutation_method":"equation_flip","missing":2},
    {"model_scale":"medium","failure_type":"semantic_regression","mutation_method":"boundary_swap","missing":1}
  ]
}
JSON

python3 -m gateforge.dataset_failure_matrix_expansion_v1 \
  --mutation-coverage-matrix-summary "$OUT_DIR/matrix_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_failure_matrix_expansion_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("expansion_readiness_score"), (int, float)) else "FAIL",
    "tasks_present": "PASS" if isinstance(summary.get("planned_expansion_tasks"), int) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "expansion_status": summary.get("status"),
    "expansion_readiness_score": summary.get("expansion_readiness_score"),
    "planned_expansion_tasks": summary.get("planned_expansion_tasks"),
    "high_risk_uncovered_cells": summary.get("high_risk_uncovered_cells"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "expansion_status": payload["expansion_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
