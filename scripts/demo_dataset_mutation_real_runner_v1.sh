#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_mutation_real_runner_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/validated_mutation_manifest.json" <<'JSON'
{
  "schema_version": "validated_mutation_manifest_v1",
  "mutations": [
    {
      "mutation_id": "m_ok",
      "target_model_id": "mdl_a",
      "target_scale": "medium",
      "expected_failure_type": "simulate_error",
      "repro_command": "python3 -c \"print('ok-run')\""
    },
    {
      "mutation_id": "m_fail",
      "target_model_id": "mdl_b",
      "target_scale": "large",
      "expected_failure_type": "model_check_error",
      "repro_command": "python3 -c \"import sys; print('nonzero-run'); sys.exit(2)\""
    }
  ]
}
JSON

python3 -m gateforge.dataset_mutation_real_runner_v1 \
  --validated-mutation-manifest "$OUT_DIR/validated_mutation_manifest.json" \
  --timeout-seconds 10 \
  --max-retries 0 \
  --raw-observations-out "$OUT_DIR/raw_observations.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_mutation_real_runner_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
raw = json.loads((out / "raw_observations.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "executed_present": "PASS" if int(summary.get("executed_count", 0) or 0) >= 1 else "FAIL",
    "raw_schema_present": "PASS" if raw.get("schema_version") == "mutation_raw_observations_v1" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "runner_status": summary.get("status"),
    "executed_count": summary.get("executed_count"),
    "infra_error_count": summary.get("infra_error_count"),
    "nonzero_exit_count": summary.get("nonzero_exit_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "runner_status": summary_out["runner_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
