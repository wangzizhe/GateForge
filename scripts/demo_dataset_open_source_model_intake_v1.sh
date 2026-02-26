#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_open_source_model_intake_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/candidates.json" <<'JSON'
{
  "candidates": [
    {
      "model_id": "osm_001",
      "name": "Open Thermal Network",
      "source_url": "https://example.org/modelica/open-thermal-network",
      "license": "Apache-2.0",
      "scale_hint": "medium",
      "repro_command": "omc open_thermal_network.mo",
      "line_count": 320,
      "equation_count": 42,
      "complexity_score": 520
    },
    {
      "model_id": "osm_002",
      "name": "Legacy Unknown Model",
      "source_url": "https://example.org/modelica/legacy",
      "license": "Unknown",
      "scale_hint": "large",
      "repro_command": "omc legacy_large.mo"
    },
    {
      "model_id": "osm_003",
      "name": "Open Pump Network",
      "source_url": "https://example.org/modelica/open-pump-network",
      "license": "MIT",
      "scale_hint": "large",
      "repro_command": "omc open_pump_network.mo",
      "line_count": 510,
      "equation_count": 78,
      "complexity_score": 840
    }
  ]
}
JSON

python3 -m gateforge.dataset_open_source_model_intake_v1 \
  --candidate-catalog "$OUT_DIR/candidates.json" \
  --registry-out "$OUT_DIR/accepted_registry_rows.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_open_source_model_intake_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
accepted = json.loads((out / "accepted_registry_rows.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "accepted_present": "PASS" if int(summary.get("accepted_count", 0) or 0) >= 1 else "FAIL",
    "registry_schema_present": "PASS" if accepted.get("schema_version") == "open_source_intake_registry_rows_v1" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "intake_status": summary.get("status"),
    "accepted_count": summary.get("accepted_count"),
    "rejected_count": summary.get("rejected_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "intake_status": summary_out["intake_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
