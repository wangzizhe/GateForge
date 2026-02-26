#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_modelica_library_expansion_plan_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/open_source_intake_summary.json" <<'JSON'
{"accepted_count":4,"rejected_count":1}
JSON

cat > "$OUT_DIR/modelica_library_registry_summary.json" <<'JSON'
{"total_assets":16,"scale_counts":{"small":6,"medium":6,"large":4}}
JSON

cat > "$OUT_DIR/failure_corpus_saturation_summary.json" <<'JSON'
{"saturation_index":78.0,"total_gap_actions":2}
JSON

cat > "$OUT_DIR/large_coverage_push_v1_summary.json" <<'JSON'
{"push_target_large_cases":1}
JSON

python3 -m gateforge.dataset_modelica_library_expansion_plan_v1 \
  --open-source-intake-summary "$OUT_DIR/open_source_intake_summary.json" \
  --modelica-library-registry-summary "$OUT_DIR/modelica_library_registry_summary.json" \
  --failure-corpus-saturation-summary "$OUT_DIR/failure_corpus_saturation_summary.json" \
  --large-coverage-push-v1-summary "$OUT_DIR/large_coverage_push_v1_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_modelica_library_expansion_plan_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if summary.get("expansion_readiness_score") is not None else "FAIL",
    "target_present": "PASS" if int(summary.get("weekly_new_models_target", 0) or 0) >= 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "plan_status": summary.get("status"),
    "expansion_readiness_score": summary.get("expansion_readiness_score"),
    "weekly_new_models_target": summary.get("weekly_new_models_target"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "plan_status": payload["plan_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
