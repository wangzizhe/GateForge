#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_intake_growth_execution_board_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/advisor_summary.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "advice": {
    "suggested_action": "execute_targeted_growth_patch",
    "backlog_actions": [
      {"task_id":"t1","action_id":"add_candidates_large","priority":"P0","lane":"intake::large","target":"add_1_large_accepted"},
      {"task_id":"t2","action_id":"lane_backfill","priority":"P1","lane":"large::simulate_error","target":"add_2_mutations"}
    ]
  }
}
JSON

cat > "$OUT_DIR/history_summary.json" <<'JSON'
{"status":"NEEDS_REVIEW","latest_suggested_action":"execute_targeted_growth_patch","recovery_plan_rate":0.2}
JSON

cat > "$OUT_DIR/history_trend_summary.json" <<'JSON'
{"status":"NEEDS_REVIEW","trend":{"alerts":["recovery_plan_rate_increasing"]}}
JSON

cat > "$OUT_DIR/intake_summary.json" <<'JSON'
{"accepted_count":2,"accepted_large_count":0,"reject_rate_pct":42.0}
JSON

cat > "$OUT_DIR/matrix_summary.json" <<'JSON'
{"matrix_execution_ratio_pct":82.0}
JSON

cat > "$OUT_DIR/benchmark_v2_summary.json" <<'JSON'
{"failure_type_drift":0.14}
JSON

python3 -m gateforge.dataset_intake_growth_execution_board_v1 \
  --intake-growth-advisor-summary "$OUT_DIR/advisor_summary.json" \
  --intake-growth-advisor-history-summary "$OUT_DIR/history_summary.json" \
  --intake-growth-advisor-history-trend-summary "$OUT_DIR/history_trend_summary.json" \
  --real-model-intake-summary "$OUT_DIR/intake_summary.json" \
  --mutation-execution-matrix-summary "$OUT_DIR/matrix_summary.json" \
  --failure-distribution-benchmark-v2-summary "$OUT_DIR/benchmark_v2_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_intake_growth_execution_board_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "execution_score_present": "PASS" if isinstance(summary.get("execution_score"), (int, float)) else "FAIL",
    "tasks_present": "PASS" if isinstance(summary.get("tasks"), list) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "board_status": summary.get("status"),
    "execution_score": summary.get("execution_score"),
    "critical_open_tasks": summary.get("critical_open_tasks"),
    "projected_weeks_to_target": summary.get("projected_weeks_to_target"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "board_status": demo["board_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
