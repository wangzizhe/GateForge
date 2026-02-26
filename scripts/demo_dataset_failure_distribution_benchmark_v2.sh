#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_distribution_benchmark_v2_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/baseline_pack.json" <<'JSON'
{
  "selected_cases": [
    {"failure_type": "script_parse_error", "model_scale": "small"},
    {"failure_type": "model_check_error", "model_scale": "medium"},
    {"failure_type": "simulate_error", "model_scale": "large"},
    {"failure_type": "semantic_regression", "model_scale": "medium"}
  ]
}
JSON

cat > "$OUT_DIR/validator_summary.json" <<'JSON'
{
  "total_mutations": 6,
  "validated_count": 5,
  "uncertain_count": 1,
  "expected_match_ratio_pct": 83.33
}
JSON

cat > "$OUT_DIR/validated_manifest.json" <<'JSON'
{
  "schema_version": "validated_mutation_manifest_v1",
  "mutations": [
    {"mutation_id": "m1", "target_scale": "large", "expected_failure_type": "simulate_error", "observed_majority_failure_type": "simulate_error"},
    {"mutation_id": "m2", "target_scale": "medium", "expected_failure_type": "model_check_error", "observed_majority_failure_type": "model_check_error"},
    {"mutation_id": "m3", "target_scale": "large", "expected_failure_type": "semantic_regression", "observed_majority_failure_type": "semantic_regression"},
    {"mutation_id": "m4", "target_scale": "small", "expected_failure_type": "script_parse_error", "observed_majority_failure_type": "script_parse_error"},
    {"mutation_id": "m5", "target_scale": "medium", "expected_failure_type": "simulate_error", "observed_majority_failure_type": "simulate_error"}
  ]
}
JSON

python3 -m gateforge.dataset_failure_distribution_benchmark_v2 \
  --failure-baseline-pack "$OUT_DIR/baseline_pack.json" \
  --mutation-validator-summary "$OUT_DIR/validator_summary.json" \
  --validated-mutation-manifest "$OUT_DIR/validated_manifest.json" \
  --max-failure-type-drift 0.5 \
  --max-model-scale-drift 0.5 \
  --min-large-share-after-pct 15 \
  --min-validated-match-ratio-pct 70 \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_failure_distribution_benchmark_v2_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "drift_present": "PASS" if isinstance(summary.get("failure_type_drift"), (int, float)) and isinstance(summary.get("model_scale_drift"), (int, float)) else "FAIL",
    "after_cases_present": "PASS" if int(summary.get("total_cases_after", 0) or 0) >= 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "benchmark_v2_status": summary.get("status"),
    "total_cases_after": summary.get("total_cases_after"),
    "failure_type_drift": summary.get("failure_type_drift"),
    "model_scale_drift": summary.get("model_scale_drift"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "benchmark_v2_status": summary_out["benchmark_v2_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
