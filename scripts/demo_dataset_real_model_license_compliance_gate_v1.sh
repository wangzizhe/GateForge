#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_license_compliance_gate_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/registry.json" <<'JSON'
{
  "models": [
    {
      "model_id": "m1",
      "license_tag": "MIT",
      "source_path": "models/m1.mo",
      "checksum_sha256": "abc",
      "reproducibility": {"repro_command": "omc m1.mo"}
    },
    {
      "model_id": "m2",
      "license_tag": "UNKNOWN",
      "source_path": "models/m2.mo",
      "checksum_sha256": "def",
      "reproducibility": {"repro_command": "omc m2.mo"}
    }
  ]
}
JSON

python3 -m gateforge.dataset_real_model_license_compliance_gate_v1 \
  --real-model-registry "$OUT_DIR/registry.json" \
  --max-unknown-license-ratio-pct 60 \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_real_model_license_compliance_gate_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "model_count_present": "PASS" if int(summary.get("total_models", 0) or 0) >= 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "license_gate_status": summary.get("status"),
    "license_risk_score": summary.get("license_risk_score"),
    "source_diversity_count": summary.get("source_diversity_count"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "license_gate_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
