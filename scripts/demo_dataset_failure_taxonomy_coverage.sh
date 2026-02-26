#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_taxonomy_coverage_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/catalog_small_medium.json" <<'JSON'
{
  "cases": [
    {"id": "f01", "failure_type": "numerical_divergence", "model_scale": "small", "failure_stage": "simulation", "severity": "high"},
    {"id": "f02", "failure_type": "solver_non_convergence", "model_scale": "medium", "failure_stage": "simulation", "severity": "medium"},
    {"id": "f03", "failure_type": "boundary_condition_drift", "model_scale": "small", "failure_stage": "postprocess", "severity": "medium"}
  ]
}
JSON

cat > "$OUT_DIR/catalog_large.json" <<'JSON'
[
  {"id": "f04", "failure_type": "unit_parameter_mismatch", "model_scale": "large", "failure_stage": "compile", "severity": "high"},
  {"id": "f05", "failure_type": "stability_regression", "model_scale": "large", "failure_stage": "initialization", "severity": "critical"}
]
JSON

python3 -m gateforge.dataset_failure_taxonomy_coverage \
  --catalog "$OUT_DIR/catalog_small_medium.json" \
  --catalog "$OUT_DIR/catalog_large.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_failure_taxonomy_coverage_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "has_failure_type_counts": "PASS" if isinstance(payload.get("failure_type_counts"), dict) else "FAIL",
    "has_model_scale_counts": "PASS" if isinstance(payload.get("model_scale_counts"), dict) else "FAIL",
    "covers_medium": "PASS" if int((payload.get("model_scale_counts") or {}).get("medium", 0) or 0) > 0 else "FAIL",
    "covers_large": "PASS" if int((payload.get("model_scale_counts") or {}).get("large", 0) or 0) > 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "coverage_status": payload.get("status"),
    "total_cases": payload.get("total_cases"),
    "missing_failure_types_count": len(payload.get("missing_failure_types") or []),
    "missing_model_scales_count": len(payload.get("missing_model_scales") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Failure Taxonomy Coverage Demo",
            "",
            f"- coverage_status: `{demo['coverage_status']}`",
            f"- total_cases: `{demo['total_cases']}`",
            f"- missing_failure_types_count: `{demo['missing_failure_types_count']}`",
            f"- missing_model_scales_count: `{demo['missing_model_scales_count']}`",
            f"- bundle_status: `{demo['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "coverage_status": demo["coverage_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
