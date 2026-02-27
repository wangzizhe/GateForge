#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_modelica_mutation_recipe_library_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/saturation.json" <<'JSON'
{
  "target_failure_types": ["simulate_error", "model_check_error", "semantic_regression"]
}
JSON

cat > "$OUT_DIR/balance.json" <<'JSON'
{
  "missing_failure_types": ["semantic_regression"]
}
JSON

cat > "$OUT_DIR/ladder.json" <<'JSON'
{
  "large_ready": true
}
JSON

python3 -m gateforge.dataset_modelica_mutation_recipe_library_v1 \
  --failure-corpus-saturation-summary "$OUT_DIR/saturation.json" \
  --mutation-portfolio-balance-summary "$OUT_DIR/balance.json" \
  --model-scale-ladder-summary "$OUT_DIR/ladder.json" \
  --recipes-out "$OUT_DIR/recipes.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_modelica_mutation_recipe_library_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
recipes = json.loads((out / "recipes.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "recipes_generated": "PASS" if int(summary.get("total_recipes", 0) or 0) >= 1 else "FAIL",
    "schema_present": "PASS" if recipes.get("schema_version") == "modelica_mutation_recipe_library_v1" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({"recipe_library_status": summary.get("status"), "bundle_status": bundle_status, "result_flags": flags}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "recipe_library_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
