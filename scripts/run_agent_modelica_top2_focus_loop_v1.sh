#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_TOP2_FOCUS_OUT_DIR:-artifacts/agent_modelica_top2_focus_loop_v1}"
WEEK_TAG="${GATEFORGE_AGENT_WEEK_TAG:-$(date -u +%G-W%V)}"
BASE_PLAYBOOK="${GATEFORGE_AGENT_BASE_PLAYBOOK:-artifacts/agent_modelica_repair_playbook_v1/playbook.json}"
TASKSET="${GATEFORGE_AGENT_TOP2_TASKSET:-artifacts/agent_modelica_weekly_chain_v1/tasksets/evidence_taskset_${WEEK_TAG}.json}"
SWEEP_SUMMARY="${GATEFORGE_AGENT_TOP2_SWEEP_SUMMARY:-artifacts/agent_modelica_top2_weight_sweep_v1/summary.json}"
OUTCOME_WEIGHT="${GATEFORGE_AGENT_TOP2_OUTCOME_WEIGHT:-}"
STRATEGY_WEIGHT="${GATEFORGE_AGENT_TOP2_STRATEGY_WEIGHT:-}"
STRATEGY_TARGET_SCORE="${GATEFORGE_AGENT_TOP2_STRATEGY_TARGET_SCORE:-}"

if [ ! -f "$TASKSET" ]; then
  echo "Evidence taskset not found: $TASKSET" >&2
  exit 1
fi
if [ ! -f "$BASE_PLAYBOOK" ]; then
  echo "Base playbook not found: $BASE_PLAYBOOK" >&2
  exit 1
fi

if { [ -z "$OUTCOME_WEIGHT" ] || [ -z "$STRATEGY_WEIGHT" ] || [ -z "$STRATEGY_TARGET_SCORE" ]; } && [ -f "$SWEEP_SUMMARY" ]; then
  read -r SWEEP_OUTCOME SWEEP_STRATEGY SWEEP_TARGET <<EOF
$(python3 - <<'PY' "$SWEEP_SUMMARY"
import json
import sys
from pathlib import Path

p = Path(sys.argv[1])
if not p.exists():
    print("")
    raise SystemExit(0)
payload = json.loads(p.read_text(encoding="utf-8"))
cfg = payload.get("best_config") if isinstance(payload.get("best_config"), dict) else {}
print(f"{cfg.get('outcome_weight', '')} {cfg.get('strategy_weight', '')} {cfg.get('strategy_target_score', '')}")
PY
)
EOF
  if [ -z "$OUTCOME_WEIGHT" ] && [ -n "${SWEEP_OUTCOME:-}" ]; then
    OUTCOME_WEIGHT="$SWEEP_OUTCOME"
  fi
  if [ -z "$STRATEGY_WEIGHT" ] && [ -n "${SWEEP_STRATEGY:-}" ]; then
    STRATEGY_WEIGHT="$SWEEP_STRATEGY"
  fi
  if [ -z "$STRATEGY_TARGET_SCORE" ] && [ -n "${SWEEP_TARGET:-}" ]; then
    STRATEGY_TARGET_SCORE="$SWEEP_TARGET"
  fi
fi

OUTCOME_WEIGHT="${OUTCOME_WEIGHT:-0.7}"
STRATEGY_WEIGHT="${STRATEGY_WEIGHT:-0.3}"
STRATEGY_TARGET_SCORE="${STRATEGY_TARGET_SCORE:-0.8}"

mkdir -p "$OUT_DIR"
export OUT_DIR WEEK_TAG OUTCOME_WEIGHT STRATEGY_WEIGHT STRATEGY_TARGET_SCORE

python3 -m gateforge.agent_modelica_strategy_ab_test_v1 \
  --taskset "$TASKSET" \
  --treatment-playbook "$BASE_PLAYBOOK" \
  --mode evidence \
  --out-dir "$OUT_DIR/before" \
  --out "$OUT_DIR/ab_before.json" \
  --report-out "$OUT_DIR/ab_before.md"

python3 -m gateforge.agent_modelica_top_failure_queue_v1 \
  --ab-summary "$OUT_DIR/ab_before.json" \
  --top-k 2 \
  --outcome-weight "$OUTCOME_WEIGHT" \
  --strategy-weight "$STRATEGY_WEIGHT" \
  --strategy-target-score "$STRATEGY_TARGET_SCORE" \
  --out "$OUT_DIR/top2_queue.json" \
  --report-out "$OUT_DIR/top2_queue.md"

python3 -m gateforge.agent_modelica_playbook_focus_update_v1 \
  --playbook "$BASE_PLAYBOOK" \
  --queue "$OUT_DIR/top2_queue.json" \
  --out "$OUT_DIR/focused_playbook.json" \
  --report-out "$OUT_DIR/focused_playbook.md"

python3 -m gateforge.agent_modelica_strategy_ab_test_v1 \
  --taskset "$TASKSET" \
  --treatment-playbook "$OUT_DIR/focused_playbook.json" \
  --mode evidence \
  --out-dir "$OUT_DIR/after" \
  --out "$OUT_DIR/ab_after.json" \
  --report-out "$OUT_DIR/ab_after.md"

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["OUT_DIR"])
before = json.loads((out / "ab_before.json").read_text(encoding="utf-8"))
after = json.loads((out / "ab_after.json").read_text(encoding="utf-8"))
queue = json.loads((out / "top2_queue.json").read_text(encoding="utf-8"))

before_delta = before.get("delta") or {}
after_delta = after.get("delta") or {}

def val(d, k):
    v = d.get(k)
    return float(v) if isinstance(v, (int, float)) else None

summary = {
    "week_tag": os.environ["WEEK_TAG"],
    "status": "PASS",
    "queue": queue.get("queue", []),
    "weight_config": {
        "outcome_weight": float(os.environ.get("OUTCOME_WEIGHT", "0.7")),
        "strategy_weight": float(os.environ.get("STRATEGY_WEIGHT", "0.3")),
        "strategy_target_score": float(os.environ.get("STRATEGY_TARGET_SCORE", "0.8")),
    },
    "before_decision": before.get("decision"),
    "after_decision": after.get("decision"),
    "before_delta": before_delta,
    "after_delta": after_delta,
    "shift": {
        "median_time_to_pass_sec": (
            round(val(after_delta, "median_time_to_pass_sec") - val(before_delta, "median_time_to_pass_sec"), 2)
            if val(after_delta, "median_time_to_pass_sec") is not None and val(before_delta, "median_time_to_pass_sec") is not None
            else None
        ),
        "median_repair_rounds": (
            round(val(after_delta, "median_repair_rounds") - val(before_delta, "median_repair_rounds"), 2)
            if val(after_delta, "median_repair_rounds") is not None and val(before_delta, "median_repair_rounds") is not None
            else None
        ),
    },
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary))
PY

python3 -m gateforge.agent_modelica_next_week_focus_targets_v1 \
  --focus-summary "$OUT_DIR/summary.json" \
  --out "$OUT_DIR/next_week_focus_targets.json" \
  --report-out "$OUT_DIR/next_week_focus_targets.md"

cat "$OUT_DIR/summary.json"
