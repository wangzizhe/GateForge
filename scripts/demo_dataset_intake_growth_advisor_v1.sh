#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_intake_growth_advisor_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/intake_summary.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "accepted_count": 2,
  "accepted_large_count": 0,
  "reject_rate_pct": 52.0,
  "weekly_target_status": "NEEDS_REVIEW",
  "accepted_scale_counts": {"small":1,"medium":1,"large":0}
}
JSON

cat > "$OUT_DIR/guard_summary.json" <<'JSON'
{"status":"NEEDS_REVIEW","target_gaps":["weekly_accepted_below_target","weekly_large_accepted_below_target"]}
JSON

cat > "$OUT_DIR/matrix_summary.json" <<'JSON'
{
  "matrix_execution_ratio_pct": 78.0,
  "missing_cells": [
    {"model_scale":"large","failure_type":"simulate_error","missing_mutations":2},
    {"model_scale":"medium","failure_type":"semantic_regression","missing_mutations":1}
  ]
}
JSON

cat > "$OUT_DIR/benchmark_v2_summary.json" <<'JSON'
{"failure_type_drift":0.17}
JSON

python3 -m gateforge.dataset_intake_growth_advisor_v1 \
  --real-model-intake-summary "$OUT_DIR/intake_summary.json" \
  --real-model-intake-weekly-target-guard-summary "$OUT_DIR/guard_summary.json" \
  --mutation-execution-matrix-summary "$OUT_DIR/matrix_summary.json" \
  --failure-distribution-benchmark-v2-summary "$OUT_DIR/benchmark_v2_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_intake_growth_advisor_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
advice = summary.get("advice") or {}
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "suggested_action_present": "PASS" if isinstance(advice.get("suggested_action"), str) else "FAIL",
    "backlog_actions_present": "PASS" if isinstance(advice.get("backlog_actions"), list) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "advisor_status": summary.get("status"),
    "suggested_action": advice.get("suggested_action"),
    "backlog_action_count": len(advice.get("backlog_actions") or []),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "advisor_status": demo["advisor_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
