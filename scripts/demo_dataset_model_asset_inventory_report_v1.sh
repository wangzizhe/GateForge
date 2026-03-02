#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_model_asset_inventory_report_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

python3 -m gateforge.dataset_model_asset_inventory_report_v1 \
  --model-glob "examples/openmodelica/**/*.mo" \
  --model-glob "artifacts/dataset_real_model_intake_pipeline_v1_demo/*.mo" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_model_asset_inventory_report_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "total_present": "PASS" if isinstance(summary.get("total_models"), int) else "FAIL",
    "scale_present": "PASS" if isinstance(summary.get("by_scale"), dict) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "inventory_status": summary.get("status"),
    "total_models": summary.get("total_models"),
    "by_scale": summary.get("by_scale"),
    "by_origin": summary.get("by_origin"),
    "inventory_fingerprint": summary.get("inventory_fingerprint"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "inventory_status": payload["inventory_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
