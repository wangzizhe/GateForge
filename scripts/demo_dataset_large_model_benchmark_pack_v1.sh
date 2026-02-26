#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_large_model_benchmark_pack_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/modelica_library_registry.json" <<'JSON'
{
  "schema_version": "modelica_library_registry_v1",
  "models": [
    {"model_id":"mdl_l1","asset_type":"model_source","suggested_scale":"large","complexity":{"complexity_score":140}},
    {"model_id":"mdl_l2","asset_type":"model_source","suggested_scale":"large","complexity":{"complexity_score":100}},
    {"model_id":"mdl_m1","asset_type":"model_source","suggested_scale":"medium","complexity":{"complexity_score":60}}
  ]
}
JSON

cat > "$OUT_DIR/mutation_manifest.json" <<'JSON'
{
  "schema_version": "mutation_manifest_v1",
  "mutations": [
    {"mutation_id":"m1","target_model_id":"mdl_l1","target_scale":"large","expected_failure_type":"simulate_error"},
    {"mutation_id":"m2","target_model_id":"mdl_l1","target_scale":"large","expected_failure_type":"model_check_error"},
    {"mutation_id":"m3","target_model_id":"mdl_l2","target_scale":"large","expected_failure_type":"semantic_regression"},
    {"mutation_id":"m4","target_model_id":"mdl_l2","target_scale":"large","expected_failure_type":"numerical_instability"},
    {"mutation_id":"m5","target_model_id":"mdl_m1","target_scale":"medium","expected_failure_type":"simulate_error"}
  ]
}
JSON

cat > "$OUT_DIR/failure_corpus_saturation_summary.json" <<'JSON'
{"target_failure_types":["simulate_error","model_check_error","semantic_regression"],"total_gap_actions":0}
JSON

cat > "$OUT_DIR/large_coverage_push_v1_summary.json" <<'JSON'
{"push_target_large_cases":0}
JSON

python3 -m gateforge.dataset_large_model_benchmark_pack_v1 \
  --modelica-library-registry "$OUT_DIR/modelica_library_registry.json" \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --failure-corpus-saturation-summary "$OUT_DIR/failure_corpus_saturation_summary.json" \
  --large-coverage-push-v1-summary "$OUT_DIR/large_coverage_push_v1_summary.json" \
  --pack-out "$OUT_DIR/pack.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_large_model_benchmark_pack_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
pack = json.loads((out / "pack.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "models_present": "PASS" if len(pack.get("models", [])) >= 1 else "FAIL",
    "mutations_present": "PASS" if len(pack.get("mutations", [])) >= 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "pack_status": summary.get("status"),
    "pack_readiness_score": summary.get("pack_readiness_score"),
    "selected_large_models": summary.get("selected_large_models"),
    "selected_large_mutations": summary.get("selected_large_mutations"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "pack_status": payload["pack_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
