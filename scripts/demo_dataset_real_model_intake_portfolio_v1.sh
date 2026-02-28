#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_intake_portfolio_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/registry.json" <<'JSON'
{
  "schema_version": "real_model_intake_registry_rows_v1",
  "models": [
    {
      "model_id": "mdl_medium_a",
      "suggested_scale": "medium",
      "license_tag": "MIT",
      "provenance": {"source_url": "https://github.com/modelica/MediumA.mo"}
    },
    {
      "model_id": "mdl_large_a",
      "suggested_scale": "large",
      "license_tag": "Apache-2.0",
      "provenance": {"source_repo": "https://gitlab.com/example/plant"}
    },
    {
      "model_id": "mdl_small_a",
      "suggested_scale": "small",
      "license_tag": "BSD-3-Clause",
      "provenance": {"source_url": "https://example.org/models/small.mo"}
    }
  ]
}
JSON

python3 -m gateforge.dataset_real_model_intake_portfolio_v1 \
  --real-model-registry "$OUT_DIR/registry.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_real_model_intake_portfolio_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "total_present": "PASS" if isinstance(summary.get("total_real_models"), int) else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("portfolio_strength_score"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "portfolio_status": summary.get("status"),
    "total_real_models": summary.get("total_real_models"),
    "large_models": summary.get("large_models"),
    "license_clean_ratio_pct": summary.get("license_clean_ratio_pct"),
    "active_domains_count": summary.get("active_domains_count"),
    "portfolio_strength_score": summary.get("portfolio_strength_score"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "portfolio_status": payload["portfolio_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
