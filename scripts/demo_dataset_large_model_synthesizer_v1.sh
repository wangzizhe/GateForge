#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_large_model_synthesizer_v1_demo"
SRC_DIR="$OUT_DIR/src_models"
mkdir -p "$OUT_DIR" "$SRC_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$SRC_DIR/medium_probe.mo" <<'MO'
model MediumProbe
  Real x(start=1);
  Real y(start=0);
equation
  der(x) = -x + y;
  der(y) = x - 0.1*y;
end MediumProbe;
MO

cat > "$SRC_DIR/small_probe.mo" <<'MO'
model SmallProbe
  Real x(start=1);
equation
  der(x) = -x;
end SmallProbe;
MO

cat > "$OUT_DIR/registry.json" <<'JSON'
{
  "schema_version": "modelica_library_registry_v1",
  "models": [
    {
      "model_id": "mdl_medium_probe_src",
      "asset_type": "model_source",
      "source_path": "artifacts/dataset_large_model_synthesizer_v1_demo/src_models/medium_probe.mo",
      "license_tag": "Apache-2.0",
      "suggested_scale": "medium",
      "reproducibility": {"om_version": "openmodelica-1.25.5", "repro_command": "omc medium_probe.mo"}
    },
    {
      "model_id": "mdl_small_probe_src",
      "asset_type": "model_source",
      "source_path": "artifacts/dataset_large_model_synthesizer_v1_demo/src_models/small_probe.mo",
      "license_tag": "Apache-2.0",
      "suggested_scale": "small",
      "reproducibility": {"om_version": "openmodelica-1.25.5", "repro_command": "omc small_probe.mo"}
    }
  ]
}
JSON

python3 -m gateforge.dataset_large_model_synthesizer_v1 \
  --modelica-library-registry "$OUT_DIR/registry.json" \
  --target-new-large-models 3 \
  --synth-model-dir "$OUT_DIR/synth_models" \
  --registry-out "$OUT_DIR/registry_after.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_large_model_synthesizer_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
registry = json.loads((out / "registry_after.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "synthesized_present": "PASS" if int(summary.get("synthesized_count", 0) or 0) >= 1 else "FAIL",
    "large_after_present": "PASS" if int(summary.get("total_large_assets_after", 0) or 0) >= 1 else "FAIL",
    "registry_schema_present": "PASS" if registry.get("schema_version") == "modelica_library_registry_v1" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "synthesizer_status": summary.get("status"),
    "synthesized_count": summary.get("synthesized_count"),
    "total_large_assets_after": summary.get("total_large_assets_after"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "synthesizer_status": summary_out["synthesizer_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
