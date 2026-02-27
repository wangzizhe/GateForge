#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_intake_pipeline_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.mo

cat > "$OUT_DIR/medium_tank.mo" <<'MODEL'
model MediumTank
  Real x(start=1);
equation
  der(x) = -0.1*x;
end MediumTank;
MODEL

cat > "$OUT_DIR/large_plant.mo" <<'MODEL'
model LargePlant
  Real a(start=1);
  Real b(start=0);
  Real c(start=0);
equation
  der(a) = -0.2*a + b;
  der(b) = a - 0.3*b + c;
  der(c) = b - 0.1*c;
end LargePlant;
MODEL

cat > "$OUT_DIR/candidate_catalog.json" <<JSON
{
  "candidates": [
    {
      "model_id": "real_medium_tank",
      "name": "Medium Tank",
      "local_path": "$OUT_DIR/medium_tank.mo",
      "source_url": "https://example.com/medium_tank.mo",
      "license": "MIT",
      "scale_hint": "medium",
      "complexity_score": 120,
      "repro_command": "python -c \"print('medium ok')\""
    },
    {
      "model_id": "real_large_plant",
      "name": "Large Plant",
      "local_path": "$OUT_DIR/large_plant.mo",
      "source_url": "https://example.com/large_plant.mo",
      "license": "Apache-2.0",
      "scale_hint": "large",
      "complexity_score": 180,
      "repro_command": "python -c \"print('large ok')\""
    }
  ]
}
JSON

python3 -m gateforge.dataset_real_model_intake_pipeline_v1 \
  --candidate-catalog "$OUT_DIR/candidate_catalog.json" \
  --registry-rows-out "$OUT_DIR/accepted_registry_rows.json" \
  --ledger-out "$OUT_DIR/intake_ledger.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_real_model_intake_pipeline_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
rows = json.loads((out / "accepted_registry_rows.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "accepted_nonzero": "PASS" if int(summary.get("accepted_count", 0) or 0) >= 1 else "FAIL",
    "rows_schema": "PASS" if rows.get("schema_version") == "real_model_intake_registry_rows_v1" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "intake_status": summary.get("status"),
    "accepted_count": summary.get("accepted_count"),
    "probe_fail_count": summary.get("probe_fail_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "intake_status": payload["intake_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
