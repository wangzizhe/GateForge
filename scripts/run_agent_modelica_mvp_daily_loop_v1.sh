#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_MVP_DAILY_LOOP_OUT_DIR:-artifacts/agent_modelica_mvp_daily_loop_v1}"
PROFILE_PATH="${GATEFORGE_AGENT_MVP_PROFILE_PATH:-benchmarks/agent_modelica_mvp_repair_v1.json}"
RUN_TAG="${GATEFORGE_AGENT_MVP_DAILY_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
AB_INTERVAL="${GATEFORGE_AGENT_RETRIEVAL_AB_INTERVAL:-5}"
HOLDOUT_INTERVAL="${GATEFORGE_AGENT_HOLDOUT_CHECKPOINT_INTERVAL:-10}"
ROLLING_FOCUS_ENABLE="${GATEFORGE_AGENT_MVP_DAILY_ROLLING_FOCUS_ENABLE:-1}"
ROLLING_FOCUS_MAX_AGE_RUNS="${GATEFORGE_AGENT_MVP_DAILY_FOCUS_MAX_AGE_RUNS:-3}"
ROLLING_FOCUS_DECAY="${GATEFORGE_AGENT_MVP_DAILY_FOCUS_DECAY:-0.7}"
ROLLING_FOCUS_MAX_ENTRIES="${GATEFORGE_AGENT_MVP_DAILY_FOCUS_MAX_ENTRIES:-2}"
RUN_DIR="$OUT_DIR/runs/$RUN_TAG"
LEDGER_PATH="$OUT_DIR/history.jsonl"
SUMMARY_PATH="$OUT_DIR/summary.json"
REPORT_PATH="$OUT_DIR/summary.md"
ROLLING_FOCUS_TARGETS_PATH="${GATEFORGE_AGENT_MVP_DAILY_ROLLING_FOCUS_TARGETS_PATH:-$OUT_DIR/rolling_focus_targets.json}"
PREV_FOCUS_TARGETS_PATH=""
if [ "$ROLLING_FOCUS_ENABLE" = "1" ] && [ -f "$ROLLING_FOCUS_TARGETS_PATH" ]; then
  PREV_FOCUS_TARGETS_PATH="$ROLLING_FOCUS_TARGETS_PATH"
fi

mkdir -p "$OUT_DIR/runs"

set +e
GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR="$RUN_DIR" \
GATEFORGE_AGENT_WEEK_TAG="daily_${RUN_TAG}" \
GATEFORGE_AGENT_FOCUS_TARGETS_PATH="$PREV_FOCUS_TARGETS_PATH" \
GATEFORGE_AGENT_ALLOW_BASELINE_FAIL="1" \
bash scripts/run_agent_modelica_weekly_chain_v1.sh >/tmp/gf_mvp_daily.log 2>&1
RUN_RC=$?
set -e

if [ ! -f "$RUN_DIR/summary.json" ]; then
  echo "missing daily summary: $RUN_DIR/summary.json (rc=$RUN_RC)" >&2
  exit 1
fi

python3 - "$RUN_DIR/summary.json" "$LEDGER_PATH" "$RUN_TAG" "$RUN_RC" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
ledger = Path(sys.argv[2])
run_tag = sys.argv[3]
run_rc = int(sys.argv[4])

row = {
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_tag": run_tag,
    "execution_rc": run_rc,
    "status": summary.get("status"),
    "success_at_k_pct": summary.get("success_at_k_pct"),
    "regression_count": summary.get("regression_count"),
    "physics_fail_count": summary.get("physics_fail_count"),
    "source_summary": sys.argv[1],
}
ledger.parent.mkdir(parents=True, exist_ok=True)
with ledger.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=True) + "\n")
PY

RUN_COUNT="$(wc -l < "$LEDGER_PATH" | tr -d '[:space:]')"
AB_RAN="0"
AB_SUMMARY_PATH=""
AB_RC="-1"
if [ "$AB_INTERVAL" -gt 0 ] && [ $((RUN_COUNT % AB_INTERVAL)) -eq 0 ]; then
  AB_RAN="1"
  AB_OUT_DIR="$OUT_DIR/ab_checkpoint/$RUN_TAG"
  set +e
  GATEFORGE_AGENT_RETRIEVAL_AB_OUT_DIR="$AB_OUT_DIR" \
  GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
  GATEFORGE_AGENT_RETRIEVAL_AB_TAG="$RUN_TAG" \
  bash scripts/run_agent_modelica_retrieval_ab_checkpoint_v1.sh >/tmp/gf_mvp_daily_ab.log 2>&1
  AB_RC=$?
  set -e
  AB_SUMMARY_PATH="$AB_OUT_DIR/ab_summary.json"
  if [ ! -f "$AB_SUMMARY_PATH" ]; then
    AB_SUMMARY_PATH=""
  fi
fi

HOLDOUT_RAN="0"
HOLDOUT_SUMMARY_PATH=""
HOLDOUT_RC="-1"
if [ "$HOLDOUT_INTERVAL" -gt 0 ] && [ $((RUN_COUNT % HOLDOUT_INTERVAL)) -eq 0 ]; then
  HOLDOUT_RAN="1"
  HOLDOUT_OUT_DIR="$OUT_DIR/holdout_checkpoint/$RUN_TAG"
  EXCLUDE_TASKSET_PATH=""
  if ls "$RUN_DIR"/tasksets/taskset_*.json >/dev/null 2>&1; then
    EXCLUDE_TASKSET_PATH="$(ls "$RUN_DIR"/tasksets/taskset_*.json | head -n 1)"
  fi
  set +e
  GATEFORGE_AGENT_HOLDOUT_CHECKPOINT_OUT_DIR="$HOLDOUT_OUT_DIR" \
  GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
  GATEFORGE_AGENT_HOLDOUT_EXCLUDE_TASKSET="$EXCLUDE_TASKSET_PATH" \
  bash scripts/run_agent_modelica_holdout_checkpoint_v1.sh >/tmp/gf_mvp_daily_holdout.log 2>&1
  HOLDOUT_RC=$?
  set -e
  HOLDOUT_SUMMARY_PATH="$HOLDOUT_OUT_DIR/summary.json"
  if [ ! -f "$HOLDOUT_SUMMARY_PATH" ]; then
    HOLDOUT_SUMMARY_PATH=""
  fi
fi

CHECKPOINT_DECISION_PATH=""
CHECKPOINT_OUT_DIR="$OUT_DIR/checkpoint_gate/$RUN_TAG"
CHECKPOINT_RC="-1"
mkdir -p "$CHECKPOINT_OUT_DIR"
CHECKPOINT_CMD=(
  python3 -m gateforge.agent_modelica_mvp_checkpoint_gate_v1
  --daily-summary "$RUN_DIR/summary.json"
  --out "$CHECKPOINT_OUT_DIR/decision.json"
  --report-out "$CHECKPOINT_OUT_DIR/decision.md"
)
if [ -n "$AB_SUMMARY_PATH" ] && [ -f "$AB_SUMMARY_PATH" ]; then
  CHECKPOINT_CMD+=(--retrieval-ab-summary "$AB_SUMMARY_PATH")
fi
if [ -n "$HOLDOUT_SUMMARY_PATH" ] && [ -f "$HOLDOUT_SUMMARY_PATH" ]; then
  CHECKPOINT_CMD+=(--holdout-summary "$HOLDOUT_SUMMARY_PATH")
fi
set +e
"${CHECKPOINT_CMD[@]}" >/tmp/gf_mvp_daily_gate.log 2>&1
CHECKPOINT_RC=$?
set -e
if [ -f "$CHECKPOINT_OUT_DIR/decision.json" ]; then
  CHECKPOINT_DECISION_PATH="$CHECKPOINT_OUT_DIR/decision.json"
fi

NEXT_FOCUS_TARGETS_PATH=""
if [ "$HOLDOUT_RAN" = "1" ] && [ -f "$OUT_DIR/holdout_checkpoint/$RUN_TAG/focus_templates.json" ]; then
  NEXT_FOCUS_TARGETS_PATH="$OUT_DIR/holdout_checkpoint/$RUN_TAG/focus_templates.json"
elif [ -f "$RUN_DIR/weekly/top_focus_templates.json" ]; then
  NEXT_FOCUS_TARGETS_PATH="$RUN_DIR/weekly/top_focus_templates.json"
fi
if [ -n "$NEXT_FOCUS_TARGETS_PATH" ]; then
  if [ "$ROLLING_FOCUS_ENABLE" = "1" ]; then
    python3 - "$NEXT_FOCUS_TARGETS_PATH" "$PREV_FOCUS_TARGETS_PATH" "$ROLLING_FOCUS_TARGETS_PATH" "$RUN_COUNT" "$ROLLING_FOCUS_MAX_AGE_RUNS" "$ROLLING_FOCUS_DECAY" "$ROLLING_FOCUS_MAX_ENTRIES" <<'PY'
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def _load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _rows(payload: dict) -> list[dict]:
    for key in ("templates", "queue", "targets"):
        rows = payload.get(key) if isinstance(payload.get(key), list) else []
        if rows:
            return [x for x in rows if isinstance(x, dict)]
    return []


new_payload = _load(sys.argv[1])
prev_payload = _load(sys.argv[2]) if str(sys.argv[2]).strip() else {}
out = Path(sys.argv[3])
run_count = int(sys.argv[4])
max_age = max(0, int(sys.argv[5]))
decay = min(1.0, max(0.0, float(sys.argv[6])))
max_entries = max(1, int(sys.argv[7]))

merged: dict[tuple[str, str], dict] = {}
for source_name, payload in (("prev", prev_payload), ("new", new_payload)):
    rows = _rows(payload)
    for row in rows:
        ftype = str(row.get("failure_type") or "").strip().lower()
        gate = str(row.get("gate_break_reason") or "unknown_fail").strip().lower()
        if not ftype:
            continue
        key = (ftype, gate)
        base = _safe_float(row.get("priority_score"), 0.0)
        if source_name == "prev":
            prev_seen = int(row.get("last_seen_run_count", 0) or 0)
            age = max(0, run_count - prev_seen)
            if max_age > 0 and age > max_age:
                continue
            weighted = base * (math.pow(decay, age) if age > 0 else 1.0)
        else:
            weighted = base
        old = merged.get(key)
        if old is None or _safe_float(old.get("weighted_priority_score"), -1.0) < weighted:
            next_row = dict(row)
            next_row["weighted_priority_score"] = round(weighted, 4)
            next_row["last_seen_run_count"] = run_count
            merged[key] = next_row

ranked = sorted(
    merged.values(),
    key=lambda x: (
        -_safe_float(x.get("weighted_priority_score"), 0.0),
        -_safe_float(x.get("priority_score"), 0.0),
        str(x.get("failure_type") or ""),
    ),
)[:max_entries]
for idx, row in enumerate(ranked, start=1):
    row["rank"] = idx

payload = {
    "schema_version": "agent_modelica_mvp_daily_rolling_focus_v1",
    "status": "PASS" if ranked else "NEEDS_REVIEW",
    "generated_for_run_count": run_count,
    "config": {
        "max_age_runs": max_age,
        "decay": decay,
        "max_entries": max_entries,
    },
    "templates": ranked,
    "sources": {
        "new_focus_source": sys.argv[1],
        "previous_focus_source": sys.argv[2] if str(sys.argv[2]).strip() else None,
    },
}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"status": payload.get("status"), "template_count": len(ranked)}))
PY
  fi
fi

python3 - "$RUN_DIR/summary.json" "$SUMMARY_PATH" "$REPORT_PATH" "$RUN_TAG" "$RUN_COUNT" "$AB_RAN" "$AB_SUMMARY_PATH" "$AB_RC" "$RUN_RC" "$HOLDOUT_RAN" "$HOLDOUT_SUMMARY_PATH" "$HOLDOUT_RC" "$CHECKPOINT_DECISION_PATH" "$CHECKPOINT_RC" "$PREV_FOCUS_TARGETS_PATH" "$NEXT_FOCUS_TARGETS_PATH" "$RUN_DIR/baseline/run_results.json" "$ROLLING_FOCUS_ENABLE" "$ROLLING_FOCUS_MAX_AGE_RUNS" "$ROLLING_FOCUS_DECAY" "$ROLLING_FOCUS_MAX_ENTRIES" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

daily = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(sys.argv[2])
report = Path(sys.argv[3])
run_tag = sys.argv[4]
run_count = int(sys.argv[5])
ab_ran = bool(int(sys.argv[6]))
ab_summary = sys.argv[7]
ab_rc = int(sys.argv[8])
run_rc = int(sys.argv[9])
holdout_ran = bool(int(sys.argv[10]))
holdout_summary = sys.argv[11]
holdout_rc = int(sys.argv[12])
checkpoint_decision = sys.argv[13]
checkpoint_rc = int(sys.argv[14])
focus_targets_in_path = sys.argv[15]
focus_targets_out_path = sys.argv[16]
run_results_path = sys.argv[17]
rolling_focus_enable = bool(int(sys.argv[18]))
rolling_focus_max_age_runs = int(sys.argv[19])
rolling_focus_decay = float(sys.argv[20])
rolling_focus_max_entries = int(sys.argv[21])

holdout = {}
if holdout_summary:
    p = Path(holdout_summary)
    if p.exists():
        holdout = json.loads(p.read_text(encoding="utf-8"))

decision = {}
if checkpoint_decision:
    p = Path(checkpoint_decision)
    if p.exists():
        decision = json.loads(p.read_text(encoding="utf-8"))


def _focus_rows(payload: dict) -> list[dict]:
    for key in ("templates", "queue", "targets"):
        rows = payload.get(key) if isinstance(payload.get(key), list) else []
        if rows:
            return [x for x in rows if isinstance(x, dict)]
    return []


focus_target_failure_types: set[str] = set()
if focus_targets_in_path:
    p = Path(focus_targets_in_path)
    if p.exists():
        focus_payload = json.loads(p.read_text(encoding="utf-8"))
        for row in _focus_rows(focus_payload):
            ftype = str(row.get("failure_type") or "").strip().lower()
            if ftype:
                focus_target_failure_types.add(ftype)

failed_total = 0
failed_focus_hit = 0
run_results_file = Path(run_results_path)
if run_results_file.exists():
    rr = json.loads(run_results_file.read_text(encoding="utf-8"))
    records = rr.get("records") if isinstance(rr.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]
    for rec in records:
        if bool(rec.get("passed")):
            continue
        failed_total += 1
        ftype = str(rec.get("failure_type") or "").strip().lower()
        if ftype and ftype in focus_target_failure_types:
            failed_focus_hit += 1

focus_hit_rate_pct = round((failed_focus_hit / failed_total) * 100.0, 2) if failed_total > 0 else None

payload = {
    "schema_version": "agent_modelica_mvp_daily_loop_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS" if (
        str(daily.get("status")) == "PASS"
        and run_rc == 0
        and (not ab_ran or ab_rc == 0)
        and (not holdout_ran or holdout_rc == 0)
        and checkpoint_rc == 0
    ) else "NEEDS_REVIEW",
    "run_tag": run_tag,
    "run_count": run_count,
    "execution_rc": run_rc,
    "rolling_focus_enabled": rolling_focus_enable,
    "rolling_focus_config": {
        "max_age_runs": rolling_focus_max_age_runs,
        "decay": rolling_focus_decay,
        "max_entries": rolling_focus_max_entries,
    } if rolling_focus_enable else None,
    "focus_targets_in_path": focus_targets_in_path or None,
    "focus_targets_out_path": focus_targets_out_path or None,
    "focus_target_failure_types": sorted(focus_target_failure_types) if focus_target_failure_types else [],
    "focus_hit_rate_pct": focus_hit_rate_pct,
    "failed_task_count": failed_total,
    "focus_hit_failed_task_count": failed_focus_hit,
    "ab_checkpoint_ran": ab_ran,
    "ab_summary_path": ab_summary or None,
    "ab_execution_rc": ab_rc if ab_ran else None,
    "holdout_checkpoint_ran": holdout_ran,
    "holdout_summary_path": holdout_summary or None,
    "holdout_execution_rc": holdout_rc if holdout_ran else None,
    "checkpoint_decision_path": checkpoint_decision or None,
    "checkpoint_execution_rc": checkpoint_rc,
    "checkpoint_decision": {
        "status": decision.get("status"),
        "decision": decision.get("decision"),
    } if isinstance(decision, dict) and decision else None,
    "daily": {
        "status": daily.get("status"),
        "success_at_k_pct": daily.get("success_at_k_pct"),
        "regression_count": daily.get("regression_count"),
        "physics_fail_count": daily.get("physics_fail_count"),
        "median_time_to_pass_sec": daily.get("median_time_to_pass_sec"),
    },
    "holdout": {
        "status": holdout.get("status"),
        "success_at_k_pct": holdout.get("success_at_k_pct"),
        "regression_count": holdout.get("regression_count"),
        "physics_fail_count": holdout.get("physics_fail_count"),
    } if isinstance(holdout, dict) and holdout else None,
    "source_summary": sys.argv[1],
}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
lines = [
    "# GateForge Agent Modelica MVP Daily Loop v1",
    "",
    f"- status: `{payload.get('status')}`",
    f"- run_tag: `{payload.get('run_tag')}`",
    f"- run_count: `{payload.get('run_count')}`",
    f"- execution_rc: `{payload.get('execution_rc')}`",
    f"- rolling_focus_enabled: `{payload.get('rolling_focus_enabled')}`",
    f"- focus_targets_in_path: `{payload.get('focus_targets_in_path')}`",
    f"- focus_targets_out_path: `{payload.get('focus_targets_out_path')}`",
    f"- focus_hit_rate_pct: `{payload.get('focus_hit_rate_pct')}`",
    f"- failed_task_count: `{payload.get('failed_task_count')}`",
    f"- focus_hit_failed_task_count: `{payload.get('focus_hit_failed_task_count')}`",
    f"- success_at_k_pct: `{(payload.get('daily') or {}).get('success_at_k_pct')}`",
    f"- regression_count: `{(payload.get('daily') or {}).get('regression_count')}`",
    f"- physics_fail_count: `{(payload.get('daily') or {}).get('physics_fail_count')}`",
    f"- ab_checkpoint_ran: `{payload.get('ab_checkpoint_ran')}`",
    f"- ab_execution_rc: `{payload.get('ab_execution_rc')}`",
    f"- holdout_checkpoint_ran: `{payload.get('holdout_checkpoint_ran')}`",
    f"- holdout_execution_rc: `{payload.get('holdout_execution_rc')}`",
    f"- checkpoint_execution_rc: `{payload.get('checkpoint_execution_rc')}`",
    f"- checkpoint_decision: `{(payload.get('checkpoint_decision') or {}).get('decision')}`",
    "",
]
report.write_text("\n".join(lines), encoding="utf-8")
print(json.dumps(payload))
PY

cat "$SUMMARY_PATH"
