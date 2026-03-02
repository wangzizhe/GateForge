#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_modelica_representativeness_gate_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/registry.json" <<'JSON'
{
  "models": [
    {"model_id":"mdl_s1","asset_type":"model_source","source_name":"repo_a","suggested_scale":"small","complexity":{"complexity_score":55}},
    {"model_id":"mdl_m1","asset_type":"model_source","source_name":"repo_a","suggested_scale":"medium","complexity":{"complexity_score":160}},
    {"model_id":"mdl_l1","asset_type":"model_source","source_name":"repo_b","suggested_scale":"large","complexity":{"complexity_score":320}},
    {"model_id":"mdl_l2","asset_type":"model_source","source_name":"repo_b","suggested_scale":"large","complexity":{"complexity_score":290}},
    {"model_id":"mos_1","asset_type":"model_script","source_name":"repo_b","suggested_scale":"large","complexity":{"complexity_score":40}}
  ]
}
JSON

cat > "$OUT_DIR/library_summary.json" <<JSON
{
  "status":"PASS",
  "total_assets":5,
  "model_assets_count":4,
  "registry_path":"$OUT_DIR/registry.json"
}
JSON

cat > "$OUT_DIR/inventory_summary.json" <<'JSON'
{"status":"PASS","total_models":4}
JSON

cat > "$OUT_DIR/portfolio_summary.json" <<'JSON'
{"status":"PASS","total_real_models":4}
JSON

python3 -m gateforge.dataset_modelica_representativeness_gate_v1 \
  --modelica-library-registry-summary "$OUT_DIR/library_summary.json" \
  --model-asset-inventory-report-summary "$OUT_DIR/inventory_summary.json" \
  --real-model-intake-portfolio-summary "$OUT_DIR/portfolio_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_modelica_representativeness_gate_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("representativeness_score"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "representativeness_status": summary.get("status"),
    "representativeness_score": summary.get("representativeness_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "representativeness_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
