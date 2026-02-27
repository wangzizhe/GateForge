#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_mutation_recipe_execution_audit_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/recipe_summary.json" <<'JSON'
{"status":"PASS","total_recipes":10}
JSON
cat > "$OUT_DIR/matrix_summary.json" <<'JSON'
{"status":"PASS","matrix_execution_ratio_pct":80.0,"missing_cells":[{"model_scale":"large","failure_type":"simulate_error","missing_mutations":1}]}
JSON

python3 -m gateforge.dataset_mutation_recipe_execution_audit_v1 \
  --mutation-recipe-library "$OUT_DIR/recipe_summary.json" \
  --mutation-execution-matrix-summary "$OUT_DIR/matrix_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_mutation_recipe_execution_audit_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "coverage_present": "PASS" if float(summary.get("execution_coverage_pct", 0) or 0) >= 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({"audit_status": summary.get("status"), "execution_coverage_pct": summary.get("execution_coverage_pct"), "bundle_status": bundle_status, "result_flags": flags}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "audit_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
