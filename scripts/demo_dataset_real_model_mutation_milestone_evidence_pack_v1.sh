#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_mutation_milestone_evidence_pack_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/bootstrap.json" <<'JSON'
{"status":"PASS","harvest_total_candidates":720,"accepted_models":720}
JSON

cat > "$OUT_DIR/scale_summary.json" <<'JSON'
{
  "bundle_status":"PASS",
  "scale_gate_status":"PASS",
  "accepted_models":606,
  "accepted_large_models":153,
  "generated_mutations":3780,
  "reproducible_mutations":3780,
  "mutation_validation_status":"PASS",
  "validation_backend_used":"syntax",
  "baseline_check_pass_rate_pct":100.0,
  "validation_stage_match_rate_pct":82.0,
  "validation_type_match_rate_pct":76.0,
  "selected_mutation_models":378,
  "failure_types_count":5,
  "mutations_per_failure_type":2
}
JSON

cat > "$OUT_DIR/scale_gate.json" <<'JSON'
{"status":"PASS","accepted_models":606,"generated_mutations":3780}
JSON

cat > "$OUT_DIR/source_manifest.json" <<'JSON'
{"sources":[{"source_id":"s1"},{"source_id":"s2"},{"source_id":"s3"}]}
JSON

python3 -m gateforge.dataset_real_model_mutation_milestone_evidence_pack_v1 \
  --open-source-bootstrap-summary "$OUT_DIR/bootstrap.json" \
  --scale-batch-summary "$OUT_DIR/scale_summary.json" \
  --scale-gate-summary "$OUT_DIR/scale_gate.json" \
  --source-manifest "$OUT_DIR/source_manifest.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_real_model_mutation_milestone_evidence_pack_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "claims_present": "PASS" if len(summary.get("milestone_claims") or []) >= 3 else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("evidence_score"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "bundle_status": bundle_status,
    "status": summary.get("status"),
    "publishable": summary.get("publishable"),
    "evidence_score": summary.get("evidence_score"),
    "validation_type_match_rate_pct": summary.get("validation_type_match_rate_pct"),
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "status": payload["status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
