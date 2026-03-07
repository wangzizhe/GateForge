#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_ELECTRICAL_LIVE_FOCUS_OUT_DIR:-artifacts/agent_modelica_electrical_live_focus_boost_v0}"
BENCHMARK_PATH="${GATEFORGE_AGENT_ELECTRICAL_TASKS_PATH:-benchmarks/agent_modelica_electrical_tasks_v0.json}"
SCALES="${GATEFORGE_AGENT_ELECTRICAL_SCALES:-small}"
MAX_TASKS="${GATEFORGE_AGENT_ELECTRICAL_MAX_TASKS:-6}"
FAILURE_CYCLE="${GATEFORGE_AGENT_ELECTRICAL_FAILURE_CYCLE:-model_check_error,simulate_error,semantic_regression}"
MUTATION_STYLE="${GATEFORGE_AGENT_ELECTRICAL_MUTATION_STYLE:-topology}"

MAX_ROUNDS="${GATEFORGE_AGENT_ELECTRICAL_MAX_ROUNDS:-2}"
MAX_TIME_SEC="${GATEFORGE_AGENT_ELECTRICAL_MAX_TIME_SEC:-180}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_ELECTRICAL_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_ELECTRICAL_LIVE_TIMEOUT_SEC:-180}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_ELECTRICAL_LIVE_MAX_OUTPUT_CHARS:-2400}"
OM_LIBRARY_CACHE="${GATEFORGE_AGENT_OM_LIBRARY_CACHE:-$OUT_DIR/.omlibrary_cache}"

REPAIR_MEMORY_PATH="${GATEFORGE_AGENT_REPAIR_MEMORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"
PATCH_TEMPLATE_ADAPTATIONS_PATH="${GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH:-data/private_failure_corpus/agent_modelica_patch_template_adaptations_v1.json}"
RETRIEVAL_POLICY_PATH="${GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH:-data/private_failure_corpus/agent_modelica_retrieval_policy_v1.json}"

FOCUS_TOP_K="${GATEFORGE_AGENT_FOCUS_TOP_K:-2}"
FOCUS_PERSISTENCE_WEIGHT="${GATEFORGE_AGENT_FOCUS_PERSISTENCE_WEIGHT:-3.0}"
FOCUS_SIGNAL_WEIGHT="${GATEFORGE_AGENT_FOCUS_SIGNAL_WEIGHT:-3.0}"
FOCUS_SIGNAL_TARGET_SCORE="${GATEFORGE_AGENT_FOCUS_SIGNAL_TARGET_SCORE:-0.8}"
STRATEGY_AB_SUMMARY="${GATEFORGE_AGENT_STRATEGY_AB_SUMMARY:-}"
FOCUS_HISTORY_JSONL="${GATEFORGE_AGENT_FOCUS_HISTORY_JSONL:-$OUT_DIR/focus_queue_history.jsonl}"

DEFAULT_LIVE_EXECUTOR_CMD="python3 -m gateforge.agent_modelica_live_executor_gemini_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${GATEFORGE_AGENT_LIVE_PLANNER_BACKEND:-gemini}\" --backend \"${GATEFORGE_AGENT_LIVE_OM_BACKEND:-openmodelica_docker}\" --docker-image \"${GATEFORGE_AGENT_LIVE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}\""
LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_LIVE_EXECUTOR_CMD:-$DEFAULT_LIVE_EXECUTOR_CMD}"

mkdir -p "$OUT_DIR" "$OUT_DIR/before" "$OUT_DIR/after"
mkdir -p "$OM_LIBRARY_CACHE"
OM_LIBRARY_CACHE="$(cd "$OM_LIBRARY_CACHE" && pwd)"
export GATEFORGE_OM_DOCKER_LIBRARY_CACHE="$OM_LIBRARY_CACHE"

python3 -m gateforge.agent_modelica_electrical_mutant_taskset_v0 \
  --benchmark "$BENCHMARK_PATH" \
  --scales "$SCALES" \
  --max-tasks "$MAX_TASKS" \
  --failure-cycle "$FAILURE_CYCLE" \
  --mutation-style "$MUTATION_STYLE" \
  --source-models-dir "$OUT_DIR/source_models" \
  --mutants-dir "$OUT_DIR/mutants" \
  --taskset-out "$OUT_DIR/taskset.json" \
  --out "$OUT_DIR/taskset_summary.json"

python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset "$OUT_DIR/taskset.json" \
  --mode live \
  --max-rounds "$MAX_ROUNDS" \
  --max-time-sec "$MAX_TIME_SEC" \
  --runtime-threshold "$RUNTIME_THRESHOLD" \
  --repair-history "$REPAIR_MEMORY_PATH" \
  --patch-template-adaptations "$PATCH_TEMPLATE_ADAPTATIONS_PATH" \
  --retrieval-policy "$RETRIEVAL_POLICY_PATH" \
  --live-executor-cmd "$LIVE_EXECUTOR_CMD" \
  --live-timeout-sec "$LIVE_TIMEOUT_SEC" \
  --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS" \
  --results-out "$OUT_DIR/before/run_results.json" \
  --out "$OUT_DIR/before/run_summary.json"

python3 -m gateforge.agent_modelica_failure_attribution_v1 \
  --run-results "$OUT_DIR/before/run_results.json" \
  --out "$OUT_DIR/failure_attribution.json" \
  --report-out "$OUT_DIR/failure_attribution.md"

FOCUS_QUEUE_CMD=(
  python3 -m gateforge.agent_modelica_focus_queue_from_attribution_v1
  --failure-attribution "$OUT_DIR/failure_attribution.json"
  --run-results "$OUT_DIR/before/run_results.json"
  --history-jsonl "$FOCUS_HISTORY_JSONL"
  --persistence-weight "$FOCUS_PERSISTENCE_WEIGHT"
  --strategy-signal-weight "$FOCUS_SIGNAL_WEIGHT"
  --strategy-signal-target-score "$FOCUS_SIGNAL_TARGET_SCORE"
  --append-history
  --top-k "$FOCUS_TOP_K"
  --out "$OUT_DIR/focus_queue.json"
  --report-out "$OUT_DIR/focus_queue.md"
)
if [ -n "$STRATEGY_AB_SUMMARY" ] && [ -f "$STRATEGY_AB_SUMMARY" ]; then
  FOCUS_QUEUE_CMD+=(--strategy-ab-summary "$STRATEGY_AB_SUMMARY")
fi
"${FOCUS_QUEUE_CMD[@]}"

FOCUS_TEMPLATE_CMD=(
  python3 -m gateforge.agent_modelica_focus_template_bundle_v1
  --focus-queue "$OUT_DIR/focus_queue.json"
  --top-k "$FOCUS_TOP_K"
  --out "$OUT_DIR/focus_templates.json"
  --report-out "$OUT_DIR/focus_templates.md"
)
if [ -n "$STRATEGY_AB_SUMMARY" ] && [ -f "$STRATEGY_AB_SUMMARY" ]; then
  FOCUS_TEMPLATE_CMD+=(--strategy-ab-summary "$STRATEGY_AB_SUMMARY")
fi
"${FOCUS_TEMPLATE_CMD[@]}"

python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset "$OUT_DIR/taskset.json" \
  --mode live \
  --max-rounds "$MAX_ROUNDS" \
  --max-time-sec "$MAX_TIME_SEC" \
  --runtime-threshold "$RUNTIME_THRESHOLD" \
  --repair-history "$REPAIR_MEMORY_PATH" \
  --focus-queue "$OUT_DIR/focus_queue.json" \
  --patch-template-adaptations "$PATCH_TEMPLATE_ADAPTATIONS_PATH" \
  --retrieval-policy "$RETRIEVAL_POLICY_PATH" \
  --live-executor-cmd "$LIVE_EXECUTOR_CMD" \
  --live-timeout-sec "$LIVE_TIMEOUT_SEC" \
  --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS" \
  --results-out "$OUT_DIR/after/run_results.json" \
  --out "$OUT_DIR/after/run_summary.json"

python3 -m gateforge.agent_modelica_diagnostic_quality_v0 \
  --run-results "$OUT_DIR/before/run_results.json" \
  --taskset "$OUT_DIR/taskset.json" \
  --out "$OUT_DIR/before/diagnostic_quality_summary.json"

python3 -m gateforge.agent_modelica_diagnostic_quality_v0 \
  --run-results "$OUT_DIR/after/run_results.json" \
  --taskset "$OUT_DIR/taskset.json" \
  --out "$OUT_DIR/after/diagnostic_quality_summary.json"

python3 -m gateforge.agent_modelica_repair_memory_store_v1 \
  --run-results "$OUT_DIR/after/run_results.json" \
  --taskset "$OUT_DIR/taskset.json" \
  --memory "$REPAIR_MEMORY_PATH" \
  --include-failed \
  --out "$OUT_DIR/after/repair_memory_summary.json"

python3 -m gateforge.agent_modelica_repair_capability_learner_v1 \
  --repair-memory "$REPAIR_MEMORY_PATH" \
  --out-patch-template-adaptations "$PATCH_TEMPLATE_ADAPTATIONS_PATH" \
  --out-retrieval-policy "$RETRIEVAL_POLICY_PATH" \
  --out "$OUT_DIR/after/capability_learner_summary.json"

python3 -m gateforge.agent_modelica_live_focus_boost_compare_v0 \
  --before-run-summary "$OUT_DIR/before/run_summary.json" \
  --before-run-results "$OUT_DIR/before/run_results.json" \
  --after-run-summary "$OUT_DIR/after/run_summary.json" \
  --after-run-results "$OUT_DIR/after/run_results.json" \
  --focus-queue "$OUT_DIR/focus_queue.json" \
  --focus-templates "$OUT_DIR/focus_templates.json" \
  --out "$OUT_DIR/compare_summary.json" \
  --report-out "$OUT_DIR/compare_summary.md"

export GATEFORGE_AGENT_ELECTRICAL_LIVE_FOCUS_OUT_DIR="$OUT_DIR"
python3 - <<'PY'
import json
import os
from pathlib import Path

out_dir = Path(str(os.getenv("GATEFORGE_AGENT_ELECTRICAL_LIVE_FOCUS_OUT_DIR") or "artifacts/agent_modelica_electrical_live_focus_boost_v0"))
before = json.loads((out_dir / "before" / "run_summary.json").read_text(encoding="utf-8"))
after = json.loads((out_dir / "after" / "run_summary.json").read_text(encoding="utf-8"))
cmp = json.loads((out_dir / "compare_summary.json").read_text(encoding="utf-8"))
payload = {
    "status": cmp.get("status"),
    "before_success_at_k_pct": before.get("success_at_k_pct"),
    "after_success_at_k_pct": after.get("success_at_k_pct"),
    "delta_success_at_k_pct": (cmp.get("delta") or {}).get("success_at_k_pct"),
    "before_regression_count": before.get("regression_count"),
    "after_regression_count": after.get("regression_count"),
    "delta_regression_count": (cmp.get("delta") or {}).get("regression_count"),
    "before_physics_fail_count": before.get("physics_fail_count"),
    "after_physics_fail_count": after.get("physics_fail_count"),
    "delta_physics_fail_count": (cmp.get("delta") or {}).get("physics_fail_count"),
    "focus_queue_path": str(out_dir / "focus_queue.json"),
    "compare_summary_path": str(out_dir / "compare_summary.json"),
}
print(json.dumps(payload))
PY
