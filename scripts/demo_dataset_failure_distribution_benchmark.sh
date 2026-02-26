#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_distribution_benchmark_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/before.json" <<'JSON'
{
  "cases": [
    {"id": "b01", "failure_type": "numerical_divergence", "model_scale": "small", "detected": true, "false_positive": false, "regressed": false},
    {"id": "b02", "failure_type": "solver_non_convergence", "model_scale": "medium", "detected": true, "false_positive": false, "regressed": false},
    {"id": "b03", "failure_type": "boundary_condition_drift", "model_scale": "large", "detected": true, "false_positive": false, "regressed": false},
    {"id": "b04", "failure_type": "unit_parameter_mismatch", "model_scale": "medium", "detected": false, "false_positive": false, "regressed": false},
    {"id": "b05", "failure_type": "stability_regression", "model_scale": "large", "detected": true, "false_positive": false, "regressed": true}
  ]
}
JSON

cat > "$OUT_DIR/after.json" <<'JSON'
{
  "cases": [
    {"id": "a01", "failure_type": "numerical_divergence", "model_scale": "small", "detected": true, "false_positive": false, "regressed": false},
    {"id": "a02", "failure_type": "solver_non_convergence", "model_scale": "medium", "detected": true, "false_positive": false, "regressed": false},
    {"id": "a03", "failure_type": "boundary_condition_drift", "model_scale": "large", "detected": true, "false_positive": false, "regressed": false},
    {"id": "a04", "failure_type": "unit_parameter_mismatch", "model_scale": "medium", "detected": true, "false_positive": false, "regressed": false},
    {"id": "a05", "failure_type": "stability_regression", "model_scale": "large", "detected": true, "false_positive": false, "regressed": false},
    {"id": "a06", "failure_type": "solver_non_convergence", "model_scale": "large", "detected": true, "false_positive": false, "regressed": false}
  ]
}
JSON

python3 -m gateforge.dataset_failure_distribution_benchmark \
  --before "$OUT_DIR/before.json" \
  --after "$OUT_DIR/after.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_failure_distribution_benchmark_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "has_detection_rate": "PASS" if isinstance(payload.get("detection_rate_after"), (int, float)) else "FAIL",
    "has_false_positive_rate": "PASS" if isinstance(payload.get("false_positive_rate_after"), (int, float)) else "FAIL",
    "has_distribution_drift": "PASS" if isinstance(payload.get("distribution_drift_score"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "benchmark_status": payload.get("status"),
    "detection_rate_after": payload.get("detection_rate_after"),
    "false_positive_rate_after": payload.get("false_positive_rate_after"),
    "regression_rate_after": payload.get("regression_rate_after"),
    "distribution_drift_score": payload.get("distribution_drift_score"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Failure Distribution Benchmark Demo",
            "",
            f"- benchmark_status: `{summary['benchmark_status']}`",
            f"- detection_rate_after: `{summary['detection_rate_after']}`",
            f"- false_positive_rate_after: `{summary['false_positive_rate_after']}`",
            f"- regression_rate_after: `{summary['regression_rate_after']}`",
            f"- distribution_drift_score: `{summary['distribution_drift_score']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "benchmark_status": summary["benchmark_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
