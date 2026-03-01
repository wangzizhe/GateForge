#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_anchor_model_pack_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/registry.json" <<'JSON'
{"models":[{"model_id":"m1","suggested_scale":"medium"},{"model_id":"m2","suggested_scale":"large"}]}
JSON
cat > "$OUT_DIR/manifest.json" <<'JSON'
{"mutations":[
 {"mutation_id":"c1","target_model_id":"m1","expected_failure_type":"simulate_error","mutation_type":"parameter_shift"},
 {"mutation_id":"c2","target_model_id":"m2","expected_failure_type":"solver_non_convergence","mutation_type":"equation_flip"},
 {"mutation_id":"c3","target_model_id":"m2","expected_failure_type":"semantic_regression","mutation_type":"boundary_swap"}
]}
JSON

python3 -m gateforge.dataset_anchor_model_pack_v1 \
  --real-model-registry "$OUT_DIR/registry.json" \
  --validated-mutation-manifest "$OUT_DIR/manifest.json" \
  --target-cases 3 \
  --min-large-cases 1 \
  --out "$OUT_DIR/summary.json" \
  --pack-out "$OUT_DIR/pack.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_anchor_model_pack_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("pack_quality_score"), (int, float)) else "FAIL",
    "selected_cases_present": "PASS" if isinstance(summary.get("selected_cases"), int) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "pack_status": summary.get("status"),
    "pack_quality_score": summary.get("pack_quality_score"),
    "selected_cases": summary.get("selected_cases"),
    "selected_large_cases": summary.get("selected_large_cases"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "pack_status": payload["pack_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
