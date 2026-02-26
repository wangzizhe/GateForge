#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_mutation_execution_validator_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/mutation_manifest.json" <<'JSON'
{
  "schema_version": "mutation_manifest_v1",
  "mutations": [
    {"mutation_id": "m1", "expected_failure_type": "simulate_error"},
    {"mutation_id": "m2", "expected_failure_type": "model_check_error"},
    {"mutation_id": "m3", "expected_failure_type": "semantic_regression"}
  ]
}
JSON

cat > "$OUT_DIR/replay_observations.json" <<'JSON'
{
  "observations": [
    {"mutation_id": "m1", "observed_failure_types": ["simulate_error", "simulate_error", "simulate_error"]},
    {"mutation_id": "m2", "observed_failure_types": ["model_check_error", "model_check_error", "simulate_error"]},
    {"mutation_id": "m3", "observed_failure_types": ["semantic_regression", "simulate_error", "semantic_regression"]}
  ]
}
JSON

python3 -m gateforge.dataset_mutation_execution_validator_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --replay-observations "$OUT_DIR/replay_observations.json" \
  --min-evidence-runs 3 \
  --min-majority-ratio 0.66 \
  --min-match-ratio-pct 70 \
  --validated-manifest-out "$OUT_DIR/validated_manifest.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_mutation_execution_validator_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
validated = json.loads((out / "validated_manifest.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "validated_present": "PASS" if int(summary.get("validated_count", 0) or 0) >= 1 else "FAIL",
    "validated_schema_present": "PASS" if validated.get("schema_version") == "validated_mutation_manifest_v1" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "validator_status": summary.get("status"),
    "validated_count": summary.get("validated_count"),
    "mismatch_count": summary.get("mismatch_count"),
    "uncertain_count": summary.get("uncertain_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "validator_status": summary_out["validator_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
