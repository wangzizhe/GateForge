#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_mutation_bulk_pack_builder_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/registry.json" <<'JSON'
{
  "models": [
    {"model_id":"mdl_large_1","asset_type":"model_source","suggested_scale":"large","source_path":"assets_private/modelica/large1.mo"},
    {"model_id":"mdl_large_2","asset_type":"model_source","suggested_scale":"large","source_path":"assets_private/modelica/large2.mo"},
    {"model_id":"mdl_medium_1","asset_type":"model_source","suggested_scale":"medium","source_path":"assets_private/modelica/medium1.mo"}
  ]
}
JSON

python3 -m gateforge.dataset_mutation_bulk_pack_builder_v1 \
  --model-registry "$OUT_DIR/registry.json" \
  --failure-types "simulate_error,model_check_error,semantic_regression" \
  --mutations-per-failure-type 2 \
  --manifest-out "$OUT_DIR/manifest.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_mutation_bulk_pack_builder_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutations_present": "PASS" if int(summary.get("total_mutations", 0)) >= 18 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "pack_status": summary.get("status"),
    "total_mutations": summary.get("total_mutations"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "pack_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
