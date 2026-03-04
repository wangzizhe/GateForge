#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR:-artifacts/agent_modelica_weekly_chain_v1}"
WEEK_TAG="${GATEFORGE_AGENT_WEEK_TAG:-$(date -u +%G-W%V)}"
RUN_MODE="${GATEFORGE_AGENT_RUN_MODE:-evidence}"
PHYSICS_CONTRACT="${GATEFORGE_AGENT_PHYSICS_CONTRACT:-policies/physics_contract_v0.json}"
PER_SCALE_TOTAL="${GATEFORGE_AGENT_PER_SCALE_TOTAL:-20}"
PER_SCALE_FAILURE_TARGETS="${GATEFORGE_AGENT_PER_SCALE_FAILURE_TARGETS:-7,7,6}"
REPLAY_MAX="${GATEFORGE_AGENT_REPLAY_MAX:-6}"
REPLAY_MIN_PER_FAILURE_TYPE="${GATEFORGE_AGENT_REPLAY_MIN_PER_FAILURE_TYPE:-1}"
HARDPACK_PATH="${GATEFORGE_AGENT_HARDPACK_PATH:-benchmarks/agent_modelica_hardpack_v1.json}"
USE_HARDPACK="${GATEFORGE_AGENT_USE_HARDPACK:-auto}"
DECISION_MIN_SUCCESS_DELTA="${GATEFORGE_AGENT_DECISION_MIN_SUCCESS_DELTA:-0.01}"
DECISION_MIN_TIME_DELTA="${GATEFORGE_AGENT_DECISION_MIN_TIME_DELTA:--0.01}"
DECISION_MIN_ROUNDS_DELTA="${GATEFORGE_AGENT_DECISION_MIN_ROUNDS_DELTA:--0.01}"

CORE_MANIFEST="${GATEFORGE_AGENT_CORE_MUTATION_MANIFEST:-}"
SMALL_MANIFEST="${GATEFORGE_AGENT_SMALL_MUTATION_MANIFEST:-}"

if [ -z "$CORE_MANIFEST" ]; then
  if [ -f "artifacts/run_private_model_mutation_scale_batch_v1_demo/batch/mutation_manifest.json" ]; then
    CORE_MANIFEST="artifacts/run_private_model_mutation_scale_batch_v1_demo/batch/mutation_manifest.json"
  elif [ -f "artifacts/run_private_model_mutation_largefirst_sprint_v1_demo/batch/mutation_manifest.json" ]; then
    CORE_MANIFEST="artifacts/run_private_model_mutation_largefirst_sprint_v1_demo/batch/mutation_manifest.json"
  fi
fi

if [ -z "$SMALL_MANIFEST" ]; then
  if [ -f "artifacts/run_modelica_open_source_growth_sprint_v1_demo/growth/scale/mutation_manifest.json" ]; then
    SMALL_MANIFEST="artifacts/run_modelica_open_source_growth_sprint_v1_demo/growth/scale/mutation_manifest.json"
  elif [ -f "artifacts/agent_modelica_taskset_lock_v1_demo/mutation_manifest.json" ]; then
    SMALL_MANIFEST="artifacts/agent_modelica_taskset_lock_v1_demo/mutation_manifest.json"
  fi
fi

mkdir -p "$OUT_DIR/tasksets" "$OUT_DIR/baseline" "$OUT_DIR/weekly"
export OUT_DIR
FOCUS_QUEUE_HISTORY="$OUT_DIR/weekly/focus_queue_history.jsonl"

TASKSET_PATH="$OUT_DIR/tasksets/taskset_${WEEK_TAG}.json"
TASKSET_SUMMARY="$OUT_DIR/tasksets/taskset_${WEEK_TAG}_summary.json"
EVIDENCE_TASKSET_PATH="$OUT_DIR/tasksets/evidence_taskset_${WEEK_TAG}.json"

if [ -z "${GATEFORGE_AGENT_REPAIR_PLAYBOOK:-}" ]; then
  if [ -f "artifacts/agent_modelica_strategy_ab_v1/promoted_playbook.json" ]; then
    REPAIR_PLAYBOOK="artifacts/agent_modelica_strategy_ab_v1/promoted_playbook.json"
  else
    REPAIR_PLAYBOOK="artifacts/agent_modelica_repair_playbook_v1/playbook.json"
  fi
else
  REPAIR_PLAYBOOK="${GATEFORGE_AGENT_REPAIR_PLAYBOOK}"
fi

FOCUS_QUEUE_FOR_RUN=""
FOCUS_TARGETS_PATH="${GATEFORGE_AGENT_FOCUS_TARGETS_PATH:-}"
if [ -z "$FOCUS_TARGETS_PATH" ] && [ -f "$OUT_DIR/weekly/focus_queue_from_failure.json" ]; then
  FOCUS_TARGETS_PATH="$OUT_DIR/weekly/focus_queue_from_failure.json"
elif [ -z "$FOCUS_TARGETS_PATH" ] && [ -f "artifacts/agent_modelica_top2_focus_loop_v1/next_week_focus_targets.json" ]; then
  FOCUS_TARGETS_PATH="artifacts/agent_modelica_top2_focus_loop_v1/next_week_focus_targets.json"
fi

if [ -n "$FOCUS_TARGETS_PATH" ] && [ -f "$FOCUS_TARGETS_PATH" ]; then
  FOCUSED_PLAYBOOK_PATH="$OUT_DIR/weekly/focused_playbook_from_targets.json"
  python3 -m gateforge.agent_modelica_playbook_focus_update_v1 \
    --playbook "$REPAIR_PLAYBOOK" \
    --queue "$FOCUS_TARGETS_PATH" \
    --out "$FOCUSED_PLAYBOOK_PATH" \
    --report-out "$OUT_DIR/weekly/focused_playbook_from_targets.md"
  REPAIR_PLAYBOOK="$FOCUSED_PLAYBOOK_PATH"
  FOCUS_QUEUE_FOR_RUN="$FOCUS_TARGETS_PATH"
fi

use_hardpack=0
if [ "$USE_HARDPACK" = "1" ]; then
  use_hardpack=1
elif [ "$USE_HARDPACK" = "auto" ] && [ -f "$HARDPACK_PATH" ]; then
  use_hardpack=1
fi

if [ "$use_hardpack" -eq 1 ]; then
  python3 -m gateforge.agent_modelica_hardpack_taskset_builder_v1 \
    --hardpack "$HARDPACK_PATH" \
    --taskset-out "$TASKSET_PATH" \
    --out "$TASKSET_SUMMARY" \
    --report-out "${TASKSET_SUMMARY%.json}.md"
else
  if [ -z "$CORE_MANIFEST" ] || [ -z "$SMALL_MANIFEST" ]; then
    echo "Missing manifests. Set GATEFORGE_AGENT_CORE_MUTATION_MANIFEST and GATEFORGE_AGENT_SMALL_MUTATION_MANIFEST." >&2
    exit 1
  fi
  python3 -m gateforge.agent_modelica_taskset_snapshot_v1 \
    --mutation-manifest "$CORE_MANIFEST" \
    --extra-mutation-manifest "$SMALL_MANIFEST" \
    --per-scale-total "$PER_SCALE_TOTAL" \
    --per-scale-failure-targets "$PER_SCALE_FAILURE_TARGETS" \
    --adaptive-quota \
    --snapshot-version "${WEEK_TAG}" \
    --taskset-out "$TASKSET_PATH" \
    --out "$TASKSET_SUMMARY" \
    --report-out "${TASKSET_SUMMARY%.json}.md"
fi

TASKSET_FOR_BASELINE="$TASKSET_PATH"
if [ "$RUN_MODE" = "evidence" ]; then
  python3 -m gateforge.agent_modelica_evidence_taskset_builder_v1 \
    --taskset "$TASKSET_PATH" \
    --include-scales small,medium,large \
    --per-scale-limit "$PER_SCALE_TOTAL" \
    --taskset-out "$EVIDENCE_TASKSET_PATH" \
    --out "$OUT_DIR/tasksets/evidence_taskset_${WEEK_TAG}_summary.json" \
    --report-out "$OUT_DIR/tasksets/evidence_taskset_${WEEK_TAG}_summary.md"
  TASKSET_FOR_BASELINE="$EVIDENCE_TASKSET_PATH"
fi

PREV_BASELINE_TASKSET="$OUT_DIR/baseline/taskset.json"
PREV_BASELINE_RESULTS="$OUT_DIR/baseline/run_results.json"
if [ "${REPLAY_MAX}" -gt 0 ] && [ -f "$PREV_BASELINE_TASKSET" ] && [ -f "$PREV_BASELINE_RESULTS" ]; then
  REPLAY_TASKSET_PATH="$OUT_DIR/tasksets/replay_taskset_${WEEK_TAG}.json"
  python3 -m gateforge.agent_modelica_taskset_replay_injector_v1 \
    --current-taskset "$TASKSET_FOR_BASELINE" \
    --prev-taskset "$PREV_BASELINE_TASKSET" \
    --prev-run-results "$PREV_BASELINE_RESULTS" \
    --max-replay "$REPLAY_MAX" \
    --min-per-failure-type "$REPLAY_MIN_PER_FAILURE_TYPE" \
    --out-taskset "$REPLAY_TASKSET_PATH" \
    --out "$OUT_DIR/tasksets/replay_taskset_${WEEK_TAG}_summary.json" \
    --report-out "$OUT_DIR/tasksets/replay_taskset_${WEEK_TAG}_summary.md"
  TASKSET_FOR_BASELINE="$REPLAY_TASKSET_PATH"
fi

BASELINE_CMD=(
  python3 -m gateforge.agent_modelica_layered_baseline_v1
  --taskset-in "$TASKSET_FOR_BASELINE"
  --run-mode "$RUN_MODE"
  --physics-contract "$PHYSICS_CONTRACT"
  --repair-playbook "$REPAIR_PLAYBOOK"
  --out-dir "$OUT_DIR/baseline"
  --out "$OUT_DIR/baseline/summary.json"
  --report-out "$OUT_DIR/baseline/summary.md"
)
if [ -n "$FOCUS_QUEUE_FOR_RUN" ] && [ -f "$FOCUS_QUEUE_FOR_RUN" ]; then
  BASELINE_CMD+=(--focus-queue "$FOCUS_QUEUE_FOR_RUN")
fi
"${BASELINE_CMD[@]}"

python3 -m gateforge.agent_modelica_failure_attribution_v1 \
  --run-results "$OUT_DIR/baseline/run_results.json" \
  --out "$OUT_DIR/weekly/failure_attribution.json" \
  --report-out "$OUT_DIR/weekly/failure_attribution.md"

python3 -m gateforge.agent_modelica_focus_queue_from_attribution_v1 \
  --failure-attribution "$OUT_DIR/weekly/failure_attribution.json" \
  --run-results "$OUT_DIR/baseline/run_results.json" \
  --history-jsonl "$FOCUS_QUEUE_HISTORY" \
  --append-history \
  --top-k 2 \
  --out "$OUT_DIR/weekly/focus_queue_from_failure.json" \
  --report-out "$OUT_DIR/weekly/focus_queue_from_failure.md"

python3 -m gateforge.agent_modelica_playbook_focus_update_v1 \
  --playbook "$REPAIR_PLAYBOOK" \
  --queue "$OUT_DIR/weekly/focus_queue_from_failure.json" \
  --out "$OUT_DIR/weekly/focused_playbook_from_failure.json" \
  --report-out "$OUT_DIR/weekly/focused_playbook_from_failure.md"

python3 -m gateforge.agent_modelica_weekly_metrics_page_v1 \
  --baseline-summary "$OUT_DIR/baseline/summary.json" \
  --week-tag "$WEEK_TAG" \
  --ledger "$OUT_DIR/weekly/history.jsonl" \
  --out "$OUT_DIR/weekly/page.json" \
  --report-out "$OUT_DIR/weekly/page.md"

python3 -m gateforge.agent_modelica_weekly_decision_v1 \
  --current-page "$OUT_DIR/weekly/page.json" \
  --ledger "$OUT_DIR/weekly/history.jsonl" \
  --min-success-delta-promote "$DECISION_MIN_SUCCESS_DELTA" \
  --min-time-delta-promote "$DECISION_MIN_TIME_DELTA" \
  --min-rounds-delta-promote "$DECISION_MIN_ROUNDS_DELTA" \
  --out "$OUT_DIR/weekly/decision.json" \
  --report-out "$OUT_DIR/weekly/decision.md"

python3 - <<'PY'
import json
import os
from pathlib import Path

out_dir = Path(os.environ["OUT_DIR"])
week_page = json.loads((out_dir / "weekly" / "page.json").read_text(encoding="utf-8"))
taskset = json.loads((out_dir / "tasksets" / f"taskset_{week_page.get('week_tag')}_summary.json").read_text(encoding="utf-8"))

summary = {
    "week_tag": week_page.get("week_tag"),
    "status": week_page.get("status"),
    "success_at_k_pct": week_page.get("success_at_k_pct"),
    "median_time_to_pass_sec": week_page.get("median_time_to_pass_sec"),
    "median_repair_rounds": week_page.get("median_repair_rounds"),
    "regression_count": week_page.get("regression_count"),
    "physics_fail_count": week_page.get("physics_fail_count"),
    "layered_pass_rate_pct_by_scale": week_page.get("layered_pass_rate_pct_by_scale"),
    "weekly_decision": (
        json.loads((out_dir / "weekly" / "decision.json").read_text(encoding="utf-8")).get("decision")
        if (out_dir / "weekly" / "decision.json").exists()
        else None
    ),
}
(out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary))
if str(week_page.get("status") or "") == "FAIL":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
