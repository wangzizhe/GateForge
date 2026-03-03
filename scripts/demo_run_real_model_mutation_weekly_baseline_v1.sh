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
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "weekly_status": payload["weekly_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
