#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_modelica_library_provenance_guard_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/modelica_library_registry.json" <<'JSON'
{
  "schema_version": "modelica_library_registry_v1",
  "models": [
    {
      "model_id": "mdl_a",
      "source_path": "examples/a.mo",
      "source_name": "open_source_a",
      "license_tag": "MIT",
      "checksum_sha256": "abc123",
      "reproducibility": {"om_version": "openmodelica-1.25.5", "repro_command": "omc examples/a.mo"}
    },
    {
      "model_id": "mdl_b",
      "source_path": "examples/b.mo",
      "source_name": "open_source_b",
      "license_tag": "Apache-2.0",
      "checksum_sha256": "def456",
      "reproducibility": {"om_version": "openmodelica-1.25.5", "repro_command": "omc examples/b.mo"}
    }
  ]
}
JSON

python3 -m gateforge.dataset_modelica_library_provenance_guard_v1 \
  --modelica-library-registry "$OUT_DIR/modelica_library_registry.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_modelica_library_provenance_guard_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "provenance_present": "PASS" if summary.get("provenance_completeness_pct") is not None else "FAIL",
    "license_ratio_present": "PASS" if summary.get("unknown_license_ratio_pct") is not None else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "guard_status": summary.get("status"),
    "provenance_completeness_pct": summary.get("provenance_completeness_pct"),
    "unknown_license_ratio_pct": summary.get("unknown_license_ratio_pct"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "guard_status": payload["guard_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
