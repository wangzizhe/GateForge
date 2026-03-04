#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_TWO_WEEK_REPLAY_OUT_DIR:-artifacts/agent_modelica_two_week_replay_v1}"
WEEK1_TAG="${GATEFORGE_AGENT_WEEK1_TAG:-replay_w1}"
WEEK2_TAG="${GATEFORGE_AGENT_WEEK2_TAG:-replay_w2}"
HARDPACK_PATH="${GATEFORGE_AGENT_HARDPACK_PATH:-benchmarks/agent_modelica_hardpack_v1.json}"
BASE_PLAYBOOK="${GATEFORGE_AGENT_BASE_PLAYBOOK:-artifacts/agent_modelica_repair_playbook_v1/playbook.json}"
DECISION_MIN_SUCCESS_DELTA="${GATEFORGE_AGENT_DECISION_MIN_SUCCESS_DELTA:-0.01}"
DECISION_MIN_TIME_DELTA="${GATEFORGE_AGENT_DECISION_MIN_TIME_DELTA:--0.01}"
DECISION_MIN_ROUNDS_DELTA="${GATEFORGE_AGENT_DECISION_MIN_ROUNDS_DELTA:--0.01}"

if [ ! -f "$HARDPACK_PATH" ]; then
  echo "Hardpack not found: $HARDPACK_PATH" >&2
  exit 1
fi
if [ ! -f "$BASE_PLAYBOOK" ]; then
  echo "Base playbook not found: $BASE_PLAYBOOK" >&2
  exit 1
fi

mkdir -p "$OUT_DIR/week1" "$OUT_DIR/week2" "$OUT_DIR/focus"
export OUT_DIR

# Week1 baseline on locked hardpack.
GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR="$OUT_DIR/week1" \
GATEFORGE_AGENT_WEEK_TAG="$WEEK1_TAG" \
GATEFORGE_AGENT_USE_HARDPACK=1 \
GATEFORGE_AGENT_HARDPACK_PATH="$HARDPACK_PATH" \
GATEFORGE_AGENT_REPAIR_PLAYBOOK="$BASE_PLAYBOOK" \
bash scripts/run_agent_modelica_weekly_chain_v1.sh

# Focus update between week1 and week2.
GATEFORGE_AGENT_TOP2_FOCUS_OUT_DIR="$OUT_DIR/focus" \
GATEFORGE_AGENT_WEEK_TAG="$WEEK1_TAG" \
GATEFORGE_AGENT_TOP2_TASKSET="$OUT_DIR/week1/tasksets/evidence_taskset_${WEEK1_TAG}.json" \
GATEFORGE_AGENT_BASE_PLAYBOOK="$BASE_PLAYBOOK" \
bash scripts/run_agent_modelica_top2_focus_loop_v1.sh

# Week2 run with focus targets carried over.
GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR="$OUT_DIR/week2" \
GATEFORGE_AGENT_WEEK_TAG="$WEEK2_TAG" \
GATEFORGE_AGENT_USE_HARDPACK=1 \
GATEFORGE_AGENT_HARDPACK_PATH="$HARDPACK_PATH" \
GATEFORGE_AGENT_REPAIR_PLAYBOOK="$BASE_PLAYBOOK" \
GATEFORGE_AGENT_FOCUS_TARGETS_PATH="$OUT_DIR/focus/next_week_focus_targets.json" \
bash scripts/run_agent_modelica_weekly_chain_v1.sh

python3 -m gateforge.agent_modelica_weekly_decision_v1 \
  --current-page "$OUT_DIR/week2/weekly/page.json" \
  --previous-page "$OUT_DIR/week1/weekly/page.json" \
  --min-success-delta-promote "$DECISION_MIN_SUCCESS_DELTA" \
  --min-time-delta-promote "$DECISION_MIN_TIME_DELTA" \
  --min-rounds-delta-promote "$DECISION_MIN_ROUNDS_DELTA" \
  --out "$OUT_DIR/decision.json" \
  --report-out "$OUT_DIR/decision.md"

python3 -m gateforge.agent_modelica_two_week_report_v1 \
  --week1-summary "$OUT_DIR/week1/summary.json" \
  --week2-summary "$OUT_DIR/week2/summary.json" \
  --decision "$OUT_DIR/decision.json" \
  --out "$OUT_DIR/report.json" \
  --report-out "$OUT_DIR/report.md"

python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["OUT_DIR"])
w1 = json.loads((root / "week1" / "summary.json").read_text(encoding="utf-8"))
w2 = json.loads((root / "week2" / "summary.json").read_text(encoding="utf-8"))
d = json.loads((root / "decision.json").read_text(encoding="utf-8"))
report = json.loads((root / "report.json").read_text(encoding="utf-8"))
summary = {
    "status": "PASS",
    "week1_tag": w1.get("week_tag"),
    "week2_tag": w2.get("week_tag"),
    "week1_success_at_k_pct": w1.get("success_at_k_pct"),
    "week2_success_at_k_pct": w2.get("success_at_k_pct"),
    "week1_median_time_to_pass_sec": w1.get("median_time_to_pass_sec"),
    "week2_median_time_to_pass_sec": w2.get("median_time_to_pass_sec"),
    "week1_median_repair_rounds": w1.get("median_repair_rounds"),
    "week2_median_repair_rounds": w2.get("median_repair_rounds"),
    "week1_regression_count": w1.get("regression_count"),
    "week2_regression_count": w2.get("regression_count"),
    "week1_physics_fail_count": w1.get("physics_fail_count"),
    "week2_physics_fail_count": w2.get("physics_fail_count"),
    "decision": d.get("decision"),
    "delta": report.get("delta"),
}
(root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary))
PY

cat "$OUT_DIR/summary.json"
