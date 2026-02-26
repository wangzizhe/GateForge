#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_mutation_factory_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/registry.json" <<'JSON'
{
  "schema_version": "modelica_library_registry_v1",
  "models": [
    {"model_id": "mdl_probe_small", "source_path": "models/probe_small.mo", "suggested_scale": "small"},
    {"model_id": "mdl_probe_medium", "source_path": "models/probe_medium.mo", "suggested_scale": "medium"},
    {"model_id": "mdl_probe_large", "source_path": "models/probe_large.mo", "suggested_scale": "large"}
  ]
}
JSON

cat > "$OUT_DIR/families.json" <<'JSON'
{
  "schema_version": "model_family_manifest_v1",
  "families": [
    {
      "family_id": "family_probe",
      "canonical_base": "probe",
      "member_model_ids": ["mdl_probe_small", "mdl_probe_medium", "mdl_probe_large"],
      "scale_map": {
        "small": "mdl_probe_small",
        "medium": "mdl_probe_medium",
        "large": "mdl_probe_large"
      }
    }
  ]
}
JSON

python3 -m gateforge.dataset_mutation_factory_v1 \
  --model-family-manifest "$OUT_DIR/families.json" \
  --modelica-library-registry "$OUT_DIR/registry.json" \
  --seed 99 \
  --mutations-per-model 4 \
  --manifest-out "$OUT_DIR/manifest.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_mutation_factory_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "manifest_schema_present": "PASS" if manifest.get("schema_version") == "mutation_manifest_v1" else "FAIL",
    "mutations_present": "PASS" if int(summary.get("total_mutations", 0) or 0) >= 4 else "FAIL",
    "failure_types_present": "PASS" if int(summary.get("unique_failure_types", 0) or 0) >= 4 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "mutation_factory_status": summary.get("status"),
    "total_mutations": summary.get("total_mutations"),
    "unique_failure_types": summary.get("unique_failure_types"),
    "target_large_mutations": summary.get("target_large_mutations"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "mutation_factory_status": summary_out["mutation_factory_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
