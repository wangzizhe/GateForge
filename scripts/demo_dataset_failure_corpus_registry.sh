#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_corpus_registry_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/catalog_a.json" <<'JSON'
{
  "cases": [
    {"failure_type": "numerical_divergence", "model_scale": "small", "failure_stage": "simulation", "severity": "high", "model_name": "A"},
    {"failure_type": "solver_non_convergence", "model_scale": "medium", "failure_stage": "simulation", "severity": "medium", "model_name": "B"}
  ]
}
JSON

cat > "$OUT_DIR/catalog_b.json" <<'JSON'
[
  {"failure_type": "stability_regression", "model_scale": "large", "failure_stage": "postprocess", "severity": "critical", "model_name": "C"},
  {"failure_type": "solver_non_convergence", "model_scale": "medium", "failure_stage": "simulation", "severity": "medium", "model_name": "B"}
]
JSON

python3 -m gateforge.dataset_failure_corpus_registry \
  --catalog "$OUT_DIR/catalog_a.json" \
  --catalog "$OUT_DIR/catalog_b.json" \
  --registry "$OUT_DIR/registry.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_failure_corpus_registry_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "corpus_version_present": "PASS" if isinstance(payload.get("corpus_version"), str) and len(payload.get("corpus_version")) > 0 else "FAIL",
    "scale_counts_present": "PASS" if isinstance(payload.get("model_scale_counts"), dict) else "FAIL",
    "records_present": "PASS" if int(payload.get("total_records", 0) or 0) > 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "registry_status": payload.get("status"),
    "corpus_version": payload.get("corpus_version"),
    "total_records": payload.get("total_records"),
    "duplicate_fingerprint_count": payload.get("duplicate_fingerprint_count"),
    "missing_model_scales_count": len(payload.get("missing_model_scales") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Failure Corpus Registry Demo",
            "",
            f"- registry_status: `{summary['registry_status']}`",
            f"- corpus_version: `{summary['corpus_version']}`",
            f"- total_records: `{summary['total_records']}`",
            f"- duplicate_fingerprint_count: `{summary['duplicate_fingerprint_count']}`",
            f"- missing_model_scales_count: `{summary['missing_model_scales_count']}`",
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
print(json.dumps({"bundle_status": bundle_status, "registry_status": summary["registry_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
