#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_modelica_mutation_recipe_library_v2_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/executable_pool_summary.json" <<'JSON'
{"status":"PASS","executable_unique_models":120,"executable_large_models":32}
JSON

cat > "$OUT_DIR/balance.json" <<'JSON'
{"missing_failure_types":["semantic_regression","constraint_violation"]}
JSON

python3 -m gateforge.dataset_modelica_mutation_recipe_library_v2 \
  --executable-pool-summary "$OUT_DIR/executable_pool_summary.json" \
  --mutation-portfolio-balance-summary "$OUT_DIR/balance.json" \
  --recipes-out "$OUT_DIR/recipes.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_modelica_mutation_recipe_library_v2_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
recipes = json.loads((out / "recipes.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "recipes_generated": "PASS" if int(summary.get("total_recipes", 0) or 0) >= 1 else "FAIL",
    "schema_present": "PASS" if recipes.get("schema_version") == "modelica_mutation_recipe_library_v2" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "bundle_status": bundle_status,
    "recipe_library_status": summary.get("status"),
    "total_recipes": summary.get("total_recipes"),
    "operator_family_count": summary.get("operator_family_count"),
    "expected_failure_type_count": summary.get("expected_failure_type_count"),
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "recipe_library_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
