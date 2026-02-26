#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_modelica_library_registry_v1_demo"
MODELS_DIR="$OUT_DIR/models"
mkdir -p "$OUT_DIR" "$MODELS_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$MODELS_DIR/small_probe.mo" <<'MO'
model SmallProbe
  Real x(start=1);
equation
  der(x) = -x;
end SmallProbe;
MO

cat > "$MODELS_DIR/medium_probe.mo" <<'MO'
model MediumProbe
  Real x(start=1);
  Real y(start=0);
equation
  der(x) = -x + y;
  der(y) = x - 0.2*y;
end MediumProbe;
MO

cat > "$MODELS_DIR/large_probe.mo" <<'MO'
model LargeProbe
  Real x1(start=1);
  Real x2(start=0);
  Real x3(start=0);
equation
  der(x1) = -x1 + x2;
  der(x2) = x1 - 0.3*x2 + x3;
  der(x3) = x2 - 0.1*x3;
end LargeProbe;
MO

python3 -m gateforge.dataset_modelica_library_registry_v1 \
  --model-root "$MODELS_DIR" \
  --source-name "demo_modelica_lib" \
  --license-tag "Apache-2.0" \
  --registry-out "$OUT_DIR/registry.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_modelica_library_registry_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
registry = json.loads((out / "registry.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "schema_present": "PASS" if registry.get("schema_version") == "modelica_library_registry_v1" else "FAIL",
    "assets_present": "PASS" if int(summary.get("total_assets", 0) or 0) >= 3 else "FAIL",
    "medium_large_present": "PASS" if int((summary.get("scale_counts") or {}).get("medium", 0) or 0) >= 1 and int((summary.get("scale_counts") or {}).get("large", 0) or 0) >= 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "registry_status": summary.get("status"),
    "total_assets": summary.get("total_assets"),
    "scale_counts": summary.get("scale_counts"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "registry_status": summary_out["registry_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
