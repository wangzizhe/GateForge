#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_modelica_open_source_harvest_v1_demo"
mkdir -p "$OUT_DIR/sources/lib_a/Plant" "$OUT_DIR/sources/lib_b/Grid"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md
rm -rf "$OUT_DIR/exported"

cat > "$OUT_DIR/sources/lib_a/Plant/PumpNetwork.mo" <<'EOF'
model PumpNetwork
  parameter Real k = 1.0;
  Real x;
equation
  der(x) = -k * x;
end PumpNetwork;
EOF

cat > "$OUT_DIR/sources/lib_a/Plant/Tank.mo" <<'EOF'
model Tank
  Real level;
equation
  der(level) = 0.1;
end Tank;
EOF

cat > "$OUT_DIR/sources/lib_b/Grid/Converter.mo" <<'EOF'
model Converter
  Real i;
  Real v;
equation
  i = v / 10.0;
end Converter;
EOF

cat > "$OUT_DIR/manifest.json" <<JSON
{
  "sources": [
    {
      "source_id": "lib_a",
      "mode": "local",
      "local_path": "$OUT_DIR/sources/lib_a",
      "license": "BSD-3-Clause",
      "scale_hint": "medium",
      "package_roots": ["Plant"]
    },
    {
      "source_id": "lib_b",
      "mode": "local",
      "local_path": "$OUT_DIR/sources/lib_b",
      "license": "BSD-3-Clause",
      "scale_hint": "small",
      "package_roots": ["Grid"]
    }
  ]
}
JSON

python3 -m gateforge.dataset_modelica_open_source_harvest_v1 \
  --source-manifest "$OUT_DIR/manifest.json" \
  --source-cache-root "$OUT_DIR/cache" \
  --export-root "$OUT_DIR/exported" \
  --max-models-per-source 20 \
  --catalog-out "$OUT_DIR/candidate_catalog.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 -m gateforge.dataset_open_source_model_intake_v1 \
  --candidate-catalog "$OUT_DIR/candidate_catalog.json" \
  --source-name "demo_open_source_harvest" \
  --registry-out "$OUT_DIR/accepted_registry_rows.json" \
  --out "$OUT_DIR/intake_summary.json" \
  --report-out "$OUT_DIR/intake_summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_modelica_open_source_harvest_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
intake = json.loads((out / "intake_summary.json").read_text(encoding="utf-8"))
flags = {
    "harvest_has_candidates": "PASS" if int(summary.get("total_candidates", 0) or 0) >= 3 else "FAIL",
    "intake_has_accepts": "PASS" if int(intake.get("accepted_count", 0) or 0) >= 3 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "bundle_status": bundle_status,
    "harvest_status": summary.get("status"),
    "intake_status": intake.get("status"),
    "total_candidates": summary.get("total_candidates"),
    "accepted_count": intake.get("accepted_count"),
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "accepted_count": payload["accepted_count"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
