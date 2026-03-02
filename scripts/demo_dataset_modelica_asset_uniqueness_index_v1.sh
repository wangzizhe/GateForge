#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_modelica_asset_uniqueness_index_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/registry.json" <<'JSON'
{
  "models": [
    {"model_id":"m1","asset_type":"model_source","checksum_sha256":"aaa","source_name":"repo_a","source_path":"a/A.mo"},
    {"model_id":"m2","asset_type":"model_source","checksum_sha256":"bbb","source_name":"repo_b","source_path":"b/B.mo"},
    {"model_id":"m3","asset_type":"model_source","checksum_sha256":"ccc","source_name":"repo_b","source_path":"b/C.mo"},
    {"model_id":"s1","asset_type":"model_script","checksum_sha256":"ddd","source_name":"repo_b","source_path":"b/run.mos"}
  ]
}
JSON

cat > "$OUT_DIR/library_summary.json" <<JSON
{"status":"PASS","registry_path":"$OUT_DIR/registry.json"}
JSON

cat > "$OUT_DIR/provenance_summary.json" <<'JSON'
{"status":"PASS","provenance_confidence_score":90.0}
JSON

python3 -m gateforge.dataset_modelica_asset_uniqueness_index_v1 \
  --modelica-library-registry-summary "$OUT_DIR/library_summary.json" \
  --modelica-library-provenance-guard-v1-summary "$OUT_DIR/provenance_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_modelica_asset_uniqueness_index_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "index_present": "PASS" if isinstance(summary.get("asset_uniqueness_index"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "asset_uniqueness_status": summary.get("status"),
    "asset_uniqueness_index": summary.get("asset_uniqueness_index"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "asset_uniqueness_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
