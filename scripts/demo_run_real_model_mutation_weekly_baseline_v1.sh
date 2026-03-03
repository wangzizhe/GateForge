#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/run_real_model_mutation_weekly_baseline_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md
rm -f "$OUT_DIR"/history.jsonl

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
  "validation_stage_match_rate_pct":80.0,
  "validation_type_match_rate_pct":74.0,
  "selected_mutation_models":378,
  "failure_types_count":5,
  "mutations_per_failure_type":2
}
JSON

cat > "$OUT_DIR/scale_gate.json" <<'JSON'
{"status":"PASS"}
JSON

cat > "$OUT_DIR/depth_upgrade_report.json" <<'JSON'
{"status":"PASS","upgrade_status":"UPGRADED","current_mutations_per_failure_type":4}
JSON

cat > "$OUT_DIR/intake_runner_accepted.json" <<JSON
{
  "rows": [
    {"candidate_id":"m1","model_path":"$OUT_DIR/m1.mo","source_url":"https://x/m1","expected_scale":"large"},
    {"candidate_id":"m2","model_path":"$OUT_DIR/m2.mo","source_url":"https://x/m2","expected_scale":"medium"}
  ]
}
JSON

cat > "$OUT_DIR/intake_registry_rows.json" <<JSON
{
  "models": [
    {"model_id":"m1","asset_type":"model_source","source_name":"s1","source_path":"$OUT_DIR/m1.mo","suggested_scale":"large"},
    {"model_id":"m2","asset_type":"model_source","source_name":"s1","source_path":"$OUT_DIR/m2.mo","suggested_scale":"medium"}
  ]
}
JSON

cat > "$OUT_DIR/mutation_manifest.json" <<'JSON'
{
  "mutations": [
    {"mutation_id":"x1","target_model_id":"m1","expected_failure_type":"simulate_error"},
    {"mutation_id":"x2","target_model_id":"m1","expected_failure_type":"model_check_error"},
    {"mutation_id":"x3","target_model_id":"m1","expected_failure_type":"semantic_regression"},
    {"mutation_id":"x4","target_model_id":"m1","expected_failure_type":"numerical_instability"},
    {"mutation_id":"x5","target_model_id":"m1","expected_failure_type":"constraint_violation"},
    {"mutation_id":"y1","target_model_id":"m2","expected_failure_type":"simulate_error"},
    {"mutation_id":"y2","target_model_id":"m2","expected_failure_type":"model_check_error"},
    {"mutation_id":"y3","target_model_id":"m2","expected_failure_type":"semantic_regression"},
    {"mutation_id":"y4","target_model_id":"m2","expected_failure_type":"numerical_instability"},
    {"mutation_id":"y5","target_model_id":"m2","expected_failure_type":"constraint_violation"}
  ]
}
JSON

cat > "$OUT_DIR/mutation_raw_observations.json" <<'JSON'
{
  "observations": [
    {"mutation_id":"x1","execution_status":"EXECUTED"},
    {"mutation_id":"x2","execution_status":"EXECUTED"},
    {"mutation_id":"x3","execution_status":"EXECUTED"},
    {"mutation_id":"x4","execution_status":"EXECUTED"},
    {"mutation_id":"x5","execution_status":"EXECUTED"},
    {"mutation_id":"y1","execution_status":"EXECUTED"},
    {"mutation_id":"y2","execution_status":"EXECUTED"},
    {"mutation_id":"y3","execution_status":"EXECUTED"},
    {"mutation_id":"y4","execution_status":"EXECUTED"},
    {"mutation_id":"y5","execution_status":"EXECUTED"}
  ]
}
JSON

cat > "$OUT_DIR/m1.mo" <<'EOF'
model M1
  Real x;
equation
  der(x) = -x;
end M1;
EOF

cat > "$OUT_DIR/m2.mo" <<'EOF'
model M2
  Real y;
equation
  der(y) = -0.2 * y;
end M2;
EOF

GATEFORGE_WEEK_TAG="2026-W10" \
GATEFORGE_WEEKLY_BASELINE_OUT_DIR="$OUT_DIR" \
GATEFORGE_WEEKLY_LEDGER_PATH="$OUT_DIR/history.jsonl" \
GATEFORGE_MODELICA_BOOTSTRAP_SUMMARY="$OUT_DIR/bootstrap.json" \
GATEFORGE_SCALE_BATCH_SUMMARY="$OUT_DIR/scale_summary.json" \
GATEFORGE_SCALE_GATE_SUMMARY="$OUT_DIR/scale_gate.json" \
GATEFORGE_DEPTH_UPGRADE_REPORT_SUMMARY="$OUT_DIR/depth_upgrade_report.json" \
bash scripts/run_real_model_mutation_weekly_baseline_v1.sh

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/run_real_model_mutation_weekly_baseline_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("weekly_status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "trend_present": "PASS" if summary.get("trend_status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "real_model_count_present": "PASS" if int(summary.get("real_model_count", 0) or 0) >= 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "bundle_status": bundle_status,
    "weekly_status": summary.get("weekly_status"),
    "history_status": summary.get("history_status"),
    "trend_status": summary.get("trend_status"),
    "mutation_validation_status": summary.get("mutation_validation_status"),
    "mutation_validation_fidelity_score": summary.get("mutation_validation_fidelity_score"),
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "weekly_status": payload["weekly_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
