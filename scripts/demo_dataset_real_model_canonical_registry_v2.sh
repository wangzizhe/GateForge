#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_canonical_registry_v2_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/current.json" <<'JSON'
{
  "schema_version": "real_model_executable_registry_rows_v1",
  "models": [
    {"model_id":"m1","source_path":"assets_private/modelica/open_source/a.mo","source_name":"src_a","suggested_scale":"medium","checksum_sha256":"c1","structure_hash":"s1"},
    {"model_id":"m2","source_path":"assets_private/modelica/open_source/b.mo","source_name":"src_b","suggested_scale":"large","checksum_sha256":"c2","structure_hash":"s2"}
  ]
}
JSON

cat > "$OUT_DIR/previous.json" <<'JSON'
{
  "schema_version": "real_model_canonical_registry_v2",
  "models": [
    {"canonical_id":"canon_prev_x","latest_model_id":"old","latest_scale":"small","first_seen_run_tag":"old","last_seen_run_tag":"old","seen_batches":1}
  ]
}
JSON

python3 -m gateforge.dataset_real_model_canonical_registry_v2 \
  --current-executable-registry "$OUT_DIR/current.json" \
  --previous-canonical-registry "$OUT_DIR/previous.json" \
  --run-tag "demo_run" \
  --out-registry "$OUT_DIR/registry.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_real_model_canonical_registry_v2_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "canonical_total_present": "PASS" if int(summary.get("canonical_total_models", 0) or 0) >= 1 else "FAIL",
    "net_growth_present": "PASS" if "canonical_net_growth_models" in summary else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "bundle_status": bundle_status,
    "canonical_registry_status": summary.get("status"),
    "canonical_total_models": summary.get("canonical_total_models"),
    "canonical_new_models": summary.get("canonical_new_models"),
    "canonical_net_growth_models": summary.get("canonical_net_growth_models"),
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "canonical_registry_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
