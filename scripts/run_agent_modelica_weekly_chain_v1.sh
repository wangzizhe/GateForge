#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR:-artifacts/agent_modelica_weekly_chain_v1}"
WEEK_TAG="${GATEFORGE_AGENT_WEEK_TAG:-$(date -u +%G-W%V)}"
MVP_PROFILE_PATH="${GATEFORGE_AGENT_MVP_PROFILE_PATH:-benchmarks/agent_modelica_mvp_repair_v1.json}"
MVP_PROFILE_ENABLE="${GATEFORGE_AGENT_MVP_PROFILE_ENABLE:-1}"

PROFILE_RUN_MODE=""
PROFILE_MAX_ROUNDS=""
PROFILE_MAX_TIME_SEC=""
PROFILE_RUNTIME_THRESHOLD=""
PROFILE_SMALL_MAX_TIME_SEC=""
PROFILE_MEDIUM_MAX_TIME_SEC=""
PROFILE_LARGE_MAX_TIME_SEC=""
PROFILE_SMALL_MAX_ROUNDS=""
PROFILE_MEDIUM_MAX_ROUNDS=""
PROFILE_LARGE_MAX_ROUNDS=""
PROFILE_HARDPACK_PATH=""
PROFILE_USE_HARDPACK=""
PROFILE_PER_SCALE_TOTAL=""
PROFILE_PER_SCALE_FAILURE_TARGETS=""
PROFILE_FOCUS_TOP_K=""
PROFILE_FOCUS_PERSISTENCE_WEIGHT=""
PROFILE_FOCUS_SIGNAL_WEIGHT=""
PROFILE_FOCUS_SIGNAL_TARGET_SCORE=""
PROFILE_REPAIR_HISTORY_PATH=""
PROFILE_PATCH_TEMPLATE_ADAPTATIONS_PATH=""
PROFILE_RETRIEVAL_POLICY_PATH=""
PROFILE_INJECT_HARD_FAIL_COUNT=""
PROFILE_INJECT_SLOW_PASS_COUNT=""

if [ "$MVP_PROFILE_ENABLE" = "1" ] && [ -f "$MVP_PROFILE_PATH" ]; then
  # Load profile once and expose normalized key-values to shell.
  eval "$(
    python3 - "$MVP_PROFILE_PATH" <<'PY'
import json
import shlex
import sys


def get(obj, path, default=None):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def put(name, value):
    if value is None:
        return
    if isinstance(value, list):
        value = ",".join(str(x) for x in value)
    if isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=True, sort_keys=True)
    print(f"{name}={shlex.quote(str(value))}")


with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)

per_ftype = get(payload, "taskset.per_scale_failure_targets", {})
ordered_ftypes = ["model_check_error", "simulate_error", "semantic_regression"]
csv_targets = None
if isinstance(per_ftype, dict):
    vals = []
    for key in ordered_ftypes:
        if key in per_ftype:
            vals.append(str(per_ftype.get(key)))
    if vals:
        csv_targets = ",".join(vals)

taskset_source = str(get(payload, "taskset.source", "") or "").strip().lower()
profile_use_hardpack = "1" if taskset_source == "hardpack" else None

put("PROFILE_RUN_MODE", get(payload, "run_contract.mode"))
put("PROFILE_MAX_ROUNDS", get(payload, "run_contract.max_rounds"))
put("PROFILE_MAX_TIME_SEC", get(payload, "run_contract.max_time_sec"))
put("PROFILE_RUNTIME_THRESHOLD", get(payload, "run_contract.runtime_threshold"))
put("PROFILE_SMALL_MAX_TIME_SEC", get(payload, "acceptance_budgets.small_max_time_sec"))
put("PROFILE_MEDIUM_MAX_TIME_SEC", get(payload, "acceptance_budgets.medium_max_time_sec"))
put("PROFILE_LARGE_MAX_TIME_SEC", get(payload, "acceptance_budgets.large_max_time_sec"))
put("PROFILE_SMALL_MAX_ROUNDS", get(payload, "acceptance_budgets.small_max_rounds"))
put("PROFILE_MEDIUM_MAX_ROUNDS", get(payload, "acceptance_budgets.medium_max_rounds"))
put("PROFILE_LARGE_MAX_ROUNDS", get(payload, "acceptance_budgets.large_max_rounds"))
put("PROFILE_HARDPACK_PATH", get(payload, "taskset.hardpack_path"))
put("PROFILE_USE_HARDPACK", profile_use_hardpack)
put("PROFILE_PER_SCALE_TOTAL", get(payload, "taskset.per_scale_total_target"))
put("PROFILE_PER_SCALE_FAILURE_TARGETS", csv_targets)
put("PROFILE_FOCUS_TOP_K", get(payload, "focus_queue.top_k"))
put("PROFILE_FOCUS_PERSISTENCE_WEIGHT", get(payload, "focus_queue.persistence_weight"))
put("PROFILE_FOCUS_SIGNAL_WEIGHT", get(payload, "focus_queue.signal_weight"))
put("PROFILE_FOCUS_SIGNAL_TARGET_SCORE", get(payload, "focus_queue.signal_target_score"))
put("PROFILE_REPAIR_HISTORY_PATH", get(payload, "privacy.repair_history_path"))
put("PROFILE_PATCH_TEMPLATE_ADAPTATIONS_PATH", get(payload, "privacy.patch_template_adaptations_path"))
put("PROFILE_RETRIEVAL_POLICY_PATH", get(payload, "privacy.retrieval_policy_path"))
put("PROFILE_INJECT_HARD_FAIL_COUNT", get(payload, "stress_injection.hard_fail_count"))
put("PROFILE_INJECT_SLOW_PASS_COUNT", get(payload, "stress_injection.slow_pass_count"))
PY
  )"
fi

RUN_MODE="${GATEFORGE_AGENT_RUN_MODE:-${PROFILE_RUN_MODE:-evidence}}"
LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_LIVE_EXECUTOR_CMD:-}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_LIVE_TIMEOUT_SEC:-180}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_LIVE_MAX_OUTPUT_CHARS:-1200}"
PHYSICS_CONTRACT="${GATEFORGE_AGENT_PHYSICS_CONTRACT:-policies/physics_contract_v0.json}"
PER_SCALE_TOTAL="${GATEFORGE_AGENT_PER_SCALE_TOTAL:-${PROFILE_PER_SCALE_TOTAL:-20}}"
PER_SCALE_FAILURE_TARGETS="${GATEFORGE_AGENT_PER_SCALE_FAILURE_TARGETS:-${PROFILE_PER_SCALE_FAILURE_TARGETS:-7,7,6}}"
REPLAY_MAX="${GATEFORGE_AGENT_REPLAY_MAX:-6}"
REPLAY_MIN_PER_FAILURE_TYPE="${GATEFORGE_AGENT_REPLAY_MIN_PER_FAILURE_TYPE:-1}"
HARDPACK_PATH="${GATEFORGE_AGENT_HARDPACK_PATH:-${PROFILE_HARDPACK_PATH:-benchmarks/agent_modelica_hardpack_v1.json}}"
USE_HARDPACK="${GATEFORGE_AGENT_USE_HARDPACK:-${PROFILE_USE_HARDPACK:-auto}}"
MAX_ROUNDS="${GATEFORGE_AGENT_MAX_ROUNDS:-${PROFILE_MAX_ROUNDS:-9}}"
MAX_TIME_SEC="${GATEFORGE_AGENT_MAX_TIME_SEC:-${PROFILE_MAX_TIME_SEC:-1200}}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_RUNTIME_THRESHOLD:-${PROFILE_RUNTIME_THRESHOLD:-0.2}}"
SMALL_MAX_TIME_SEC="${GATEFORGE_AGENT_SMALL_MAX_TIME_SEC:-${PROFILE_SMALL_MAX_TIME_SEC:-180}}"
MEDIUM_MAX_TIME_SEC="${GATEFORGE_AGENT_MEDIUM_MAX_TIME_SEC:-${PROFILE_MEDIUM_MAX_TIME_SEC:-420}}"
LARGE_MAX_TIME_SEC="${GATEFORGE_AGENT_LARGE_MAX_TIME_SEC:-${PROFILE_LARGE_MAX_TIME_SEC:-900}}"
SMALL_MAX_ROUNDS="${GATEFORGE_AGENT_SMALL_MAX_ROUNDS:-${PROFILE_SMALL_MAX_ROUNDS:-3}}"
MEDIUM_MAX_ROUNDS="${GATEFORGE_AGENT_MEDIUM_MAX_ROUNDS:-${PROFILE_MEDIUM_MAX_ROUNDS:-6}}"
LARGE_MAX_ROUNDS="${GATEFORGE_AGENT_LARGE_MAX_ROUNDS:-${PROFILE_LARGE_MAX_ROUNDS:-9}}"
FOCUS_TOP_K="${GATEFORGE_AGENT_FOCUS_TOP_K:-${PROFILE_FOCUS_TOP_K:-2}}"
FOCUS_PERSISTENCE_WEIGHT="${GATEFORGE_AGENT_FOCUS_PERSISTENCE_WEIGHT:-${PROFILE_FOCUS_PERSISTENCE_WEIGHT:-3.0}}"
FOCUS_SIGNAL_WEIGHT="${GATEFORGE_AGENT_FOCUS_SIGNAL_WEIGHT:-${PROFILE_FOCUS_SIGNAL_WEIGHT:-3.0}}"
FOCUS_SIGNAL_TARGET_SCORE="${GATEFORGE_AGENT_FOCUS_SIGNAL_TARGET_SCORE:-${PROFILE_FOCUS_SIGNAL_TARGET_SCORE:-0.8}}"
INJECT_HARD_FAIL_COUNT="${GATEFORGE_AGENT_INJECT_HARD_FAIL_COUNT:-${PROFILE_INJECT_HARD_FAIL_COUNT:-0}}"
INJECT_SLOW_PASS_COUNT="${GATEFORGE_AGENT_INJECT_SLOW_PASS_COUNT:-${PROFILE_INJECT_SLOW_PASS_COUNT:-0}}"
ALLOW_BASELINE_FAIL="${GATEFORGE_AGENT_ALLOW_BASELINE_FAIL:-0}"
DECISION_MIN_SUCCESS_DELTA="${GATEFORGE_AGENT_DECISION_MIN_SUCCESS_DELTA:-0.01}"
DECISION_MIN_TIME_DELTA="${GATEFORGE_AGENT_DECISION_MIN_TIME_DELTA:--0.01}"
DECISION_MIN_ROUNDS_DELTA="${GATEFORGE_AGENT_DECISION_MIN_ROUNDS_DELTA:--0.01}"
REPAIR_HISTORY_PATH="${GATEFORGE_AGENT_REPAIR_HISTORY_PATH:-${PROFILE_REPAIR_HISTORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}}"
PATCH_TEMPLATE_ADAPTATIONS_PATH="${GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH:-${PROFILE_PATCH_TEMPLATE_ADAPTATIONS_PATH:-data/private_failure_corpus/agent_modelica_patch_template_adaptations_v1.json}}"
RETRIEVAL_POLICY_PATH="${GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH:-${PROFILE_RETRIEVAL_POLICY_PATH:-data/private_failure_corpus/agent_modelica_retrieval_policy_v1.json}}"
CAPABILITY_LEARN_MIN_SUCCESS_COUNT="${GATEFORGE_AGENT_CAPABILITY_LEARN_MIN_SUCCESS_COUNT:-3}"
CAPABILITY_LEARN_TOP_ACTIONS="${GATEFORGE_AGENT_CAPABILITY_LEARN_TOP_ACTIONS:-4}"
CAPABILITY_LEARN_TOP_STRATEGIES="${GATEFORGE_AGENT_CAPABILITY_LEARN_TOP_STRATEGIES:-2}"
STRATEGY_AB_SUMMARY="${GATEFORGE_AGENT_STRATEGY_AB_SUMMARY:-}"
PREFLIGHT_ENABLE="${GATEFORGE_AGENT_PREFLIGHT_ENABLE:-1}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_HOLDOUT_RATIO:-0.15}"
SPLIT_FREEZE_SEED="${GATEFORGE_AGENT_SPLIT_FREEZE_SEED:-agent_modelica_split_v1}"
RUN_RECORDS_JSONL="${GATEFORGE_AGENT_RUN_RECORDS_JSONL:-$OUT_DIR/baseline/run_records.jsonl}"
RESUME_RUN_CONTRACT="${GATEFORGE_AGENT_RESUME_RUN_CONTRACT:-1}"
RUN_SNAPSHOT_ENABLE="${GATEFORGE_AGENT_RUN_SNAPSHOT_ENABLE:-1}"

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
export REPAIR_HISTORY_PATH PATCH_TEMPLATE_ADAPTATIONS_PATH RETRIEVAL_POLICY_PATH
FOCUS_QUEUE_HISTORY="$OUT_DIR/weekly/focus_queue_history.jsonl"

if [ "$PREFLIGHT_ENABLE" = "1" ]; then
  python3 -m gateforge.agent_modelica_learning_preflight_v1 \
    --profile "$MVP_PROFILE_PATH" \
    --core-manifest "$CORE_MANIFEST" \
    --small-manifest "$SMALL_MANIFEST" \
    --out "$OUT_DIR/weekly/preflight.json" \
    --report-out "$OUT_DIR/weekly/preflight.md"
fi

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

if [ -z "$STRATEGY_AB_SUMMARY" ] && [ -f "$OUT_DIR/ab_checkpoint/$WEEK_TAG/ab_summary.json" ]; then
  STRATEGY_AB_SUMMARY="$OUT_DIR/ab_checkpoint/$WEEK_TAG/ab_summary.json"
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

SPLIT_TASKSET_PATH="$OUT_DIR/tasksets/split_taskset_${WEEK_TAG}.json"
python3 -m gateforge.agent_modelica_taskset_split_freeze_v1 \
  --taskset-in "$TASKSET_FOR_BASELINE" \
  --holdout-ratio "$HOLDOUT_RATIO" \
  --seed "$SPLIT_FREEZE_SEED" \
  --out-taskset "$SPLIT_TASKSET_PATH" \
  --out "$OUT_DIR/tasksets/split_taskset_${WEEK_TAG}_summary.json" \
  --report-out "$OUT_DIR/tasksets/split_taskset_${WEEK_TAG}_summary.md"
TASKSET_FOR_BASELINE="$SPLIT_TASKSET_PATH"

if [ "$RUN_SNAPSHOT_ENABLE" = "1" ]; then
  RUN_SNAPSHOT_CMD=(
    python3 -m gateforge.agent_modelica_run_snapshot_v1
    --run-id "$WEEK_TAG"
    --repo-root "$ROOT_DIR"
    --profile-path "$MVP_PROFILE_PATH"
    --hardpack-path "$HARDPACK_PATH"
    --physics-contract-path "$PHYSICS_CONTRACT"
    --repair-playbook-path "$REPAIR_PLAYBOOK"
    --repair-history-path "$REPAIR_HISTORY_PATH"
    --patch-template-adaptations-path "$PATCH_TEMPLATE_ADAPTATIONS_PATH"
    --retrieval-policy-path "$RETRIEVAL_POLICY_PATH"
    --taskset-path "$TASKSET_FOR_BASELINE"
    --out "$OUT_DIR/weekly/run_snapshot.json"
    --report-out "$OUT_DIR/weekly/run_snapshot.md"
  )
  if [ -n "$CORE_MANIFEST" ] && [ -f "$CORE_MANIFEST" ]; then
    RUN_SNAPSHOT_CMD+=(--extra-file "$CORE_MANIFEST")
  fi
  if [ -n "$SMALL_MANIFEST" ] && [ -f "$SMALL_MANIFEST" ]; then
    RUN_SNAPSHOT_CMD+=(--extra-file "$SMALL_MANIFEST")
  fi
  "${RUN_SNAPSHOT_CMD[@]}"
fi

BASELINE_CMD=(
  python3 -m gateforge.agent_modelica_layered_baseline_v1
  --taskset-in "$TASKSET_FOR_BASELINE"
  --run-mode "$RUN_MODE"
  --max-rounds "$MAX_ROUNDS"
  --max-time-sec "$MAX_TIME_SEC"
  --runtime-threshold "$RUNTIME_THRESHOLD"
  --small-max-time-sec "$SMALL_MAX_TIME_SEC"
  --medium-max-time-sec "$MEDIUM_MAX_TIME_SEC"
  --large-max-time-sec "$LARGE_MAX_TIME_SEC"
  --small-max-rounds "$SMALL_MAX_ROUNDS"
  --medium-max-rounds "$MEDIUM_MAX_ROUNDS"
  --large-max-rounds "$LARGE_MAX_ROUNDS"
  --physics-contract "$PHYSICS_CONTRACT"
  --repair-playbook "$REPAIR_PLAYBOOK"
  --repair-history "$REPAIR_HISTORY_PATH"
  --patch-template-adaptations "$PATCH_TEMPLATE_ADAPTATIONS_PATH"
  --retrieval-policy "$RETRIEVAL_POLICY_PATH"
  --live-timeout-sec "$LIVE_TIMEOUT_SEC"
  --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS"
  --inject-hard-fail-count "$INJECT_HARD_FAIL_COUNT"
  --inject-slow-pass-count "$INJECT_SLOW_PASS_COUNT"
  --run-records-jsonl "$RUN_RECORDS_JSONL"
  --out-dir "$OUT_DIR/baseline"
  --out "$OUT_DIR/baseline/summary.json"
  --report-out "$OUT_DIR/baseline/summary.md"
)
if [ "$RESUME_RUN_CONTRACT" = "1" ]; then
  BASELINE_CMD+=(--resume-run-contract)
fi
if [ -n "$FOCUS_QUEUE_FOR_RUN" ] && [ -f "$FOCUS_QUEUE_FOR_RUN" ]; then
  BASELINE_CMD+=(--focus-queue "$FOCUS_QUEUE_FOR_RUN")
fi
if [ -n "$LIVE_EXECUTOR_CMD" ]; then
  BASELINE_CMD+=(--live-executor-cmd "$LIVE_EXECUTOR_CMD")
fi
if [ "$ALLOW_BASELINE_FAIL" = "1" ]; then
  set +e
  "${BASELINE_CMD[@]}"
  BASELINE_RC=$?
  set -e
  if [ "$BASELINE_RC" -ne 0 ] && [ ! -f "$OUT_DIR/baseline/summary.json" ]; then
    echo "baseline failed without summary artifact (rc=$BASELINE_RC)" >&2
    exit "$BASELINE_RC"
  fi
else
  "${BASELINE_CMD[@]}"
fi

python3 -m gateforge.agent_modelica_repair_memory_store_v1 \
  --run-results "$OUT_DIR/baseline/run_results.json" \
  --taskset "$TASKSET_FOR_BASELINE" \
  --memory "$REPAIR_HISTORY_PATH" \
  --out "$OUT_DIR/weekly/repair_memory_update.json" \
  --report-out "$OUT_DIR/weekly/repair_memory_update.md"

python3 -m gateforge.agent_modelica_repair_capability_learner_v1 \
  --repair-memory "$REPAIR_HISTORY_PATH" \
  --min-success-count-per-failure-type "$CAPABILITY_LEARN_MIN_SUCCESS_COUNT" \
  --top-actions-per-failure-type "$CAPABILITY_LEARN_TOP_ACTIONS" \
  --top-strategies-per-failure-type "$CAPABILITY_LEARN_TOP_STRATEGIES" \
  --out-patch-template-adaptations "$PATCH_TEMPLATE_ADAPTATIONS_PATH" \
  --out-retrieval-policy "$RETRIEVAL_POLICY_PATH" \
  --out "$OUT_DIR/weekly/repair_capability_learn.json" \
  --report-out "$OUT_DIR/weekly/repair_capability_learn.md"

python3 -m gateforge.agent_modelica_failure_attribution_v1 \
  --run-results "$OUT_DIR/baseline/run_results.json" \
  --out "$OUT_DIR/weekly/failure_attribution.json" \
  --report-out "$OUT_DIR/weekly/failure_attribution.md"

FOCUS_QUEUE_CMD=(
  python3 -m gateforge.agent_modelica_focus_queue_from_attribution_v1
  --failure-attribution "$OUT_DIR/weekly/failure_attribution.json"
  --run-results "$OUT_DIR/baseline/run_results.json"
  --history-jsonl "$FOCUS_QUEUE_HISTORY"
  --persistence-weight "$FOCUS_PERSISTENCE_WEIGHT"
  --strategy-signal-weight "$FOCUS_SIGNAL_WEIGHT"
  --strategy-signal-target-score "$FOCUS_SIGNAL_TARGET_SCORE"
  --append-history
  --top-k "$FOCUS_TOP_K"
  --out "$OUT_DIR/weekly/focus_queue_from_failure.json"
  --report-out "$OUT_DIR/weekly/focus_queue_from_failure.md"
)
if [ -n "$STRATEGY_AB_SUMMARY" ] && [ -f "$STRATEGY_AB_SUMMARY" ]; then
  FOCUS_QUEUE_CMD+=(--strategy-ab-summary "$STRATEGY_AB_SUMMARY")
fi
"${FOCUS_QUEUE_CMD[@]}"

python3 -m gateforge.agent_modelica_playbook_focus_update_v1 \
  --playbook "$REPAIR_PLAYBOOK" \
  --queue "$OUT_DIR/weekly/focus_queue_from_failure.json" \
  --out "$OUT_DIR/weekly/focused_playbook_from_failure.json" \
  --report-out "$OUT_DIR/weekly/focused_playbook_from_failure.md"

FOCUS_TEMPLATES_CMD=(
  python3 -m gateforge.agent_modelica_focus_template_bundle_v1
  --focus-queue "$OUT_DIR/weekly/focus_queue_from_failure.json"
  --top-k "$FOCUS_TOP_K"
  --out "$OUT_DIR/weekly/top_focus_templates.json"
  --report-out "$OUT_DIR/weekly/top_focus_templates.md"
)
if [ -n "$STRATEGY_AB_SUMMARY" ] && [ -f "$STRATEGY_AB_SUMMARY" ]; then
  FOCUS_TEMPLATES_CMD+=(--strategy-ab-summary "$STRATEGY_AB_SUMMARY")
fi
"${FOCUS_TEMPLATES_CMD[@]}"

if [ "$ALLOW_BASELINE_FAIL" = "1" ]; then
  set +e
  python3 -m gateforge.agent_modelica_weekly_metrics_page_v1 \
    --baseline-summary "$OUT_DIR/baseline/summary.json" \
    --week-tag "$WEEK_TAG" \
    --ledger "$OUT_DIR/weekly/history.jsonl" \
    --out "$OUT_DIR/weekly/page.json" \
    --report-out "$OUT_DIR/weekly/page.md"
  WEEKLY_PAGE_RC=$?
  set -e
  if [ "$WEEKLY_PAGE_RC" -ne 0 ] && [ ! -f "$OUT_DIR/weekly/page.json" ]; then
    echo "weekly metrics page failed without artifact (rc=$WEEKLY_PAGE_RC)" >&2
    exit "$WEEKLY_PAGE_RC"
  fi
else
  python3 -m gateforge.agent_modelica_weekly_metrics_page_v1 \
    --baseline-summary "$OUT_DIR/baseline/summary.json" \
    --week-tag "$WEEK_TAG" \
    --ledger "$OUT_DIR/weekly/history.jsonl" \
    --out "$OUT_DIR/weekly/page.json" \
    --report-out "$OUT_DIR/weekly/page.md"
fi

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
    "repair_history_path": os.environ.get("REPAIR_HISTORY_PATH"),
    "patch_template_adaptations_path": os.environ.get("PATCH_TEMPLATE_ADAPTATIONS_PATH"),
    "retrieval_policy_path": os.environ.get("RETRIEVAL_POLICY_PATH"),
}
(out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary))
if str(week_page.get("status") or "") == "FAIL":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
