#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_mutation_depth_pressure_board_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/coverage_summary.json" <<'JSON'
{
  "status":"NEEDS_REVIEW",
  "coverage_depth_score":72.0,
  "high_risk_gaps_count":2,
  "uncovered_cells_count":4,
  "high_risk_gaps":[
    {"model_scale":"large","failure_type":"simulate_error","stage":"simulate","missing_mutations":2},
    {"model_scale":"medium","failure_type":"semantic_regression","stage":"postprocess","missing_mutations":1}
  ]
}
JSON

cat > "$OUT_DIR/audit_summary.json" <<'JSON'
{"status":"NEEDS_REVIEW","missing_recipe_count":3,"execution_coverage_pct":58.0}
JSON

cat > "$OUT_DIR/recipe_summary.json" <<'JSON'
{"status":"PASS","high_priority_recipes":4}
JSON

python3 -m gateforge.dataset_mutation_depth_pressure_board_v1 \
  --mutation-coverage-depth-summary "$OUT_DIR/coverage_summary.json" \
  --mutation-recipe-execution-audit-summary "$OUT_DIR/audit_summary.json" \
  --modelica-mutation-recipe-library-summary "$OUT_DIR/recipe_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_mutation_depth_pressure_board_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "task_present": "PASS" if isinstance(summary.get("backlog_tasks"), list) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "depth_pressure_status": summary.get("status"),
    "mutation_depth_pressure_index": summary.get("mutation_depth_pressure_index"),
    "task_count": len(summary.get("backlog_tasks") or []),
    "bundle_status": bundle_status,
    "result_flags": flags,
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "depth_pressure_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
