#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_ELECTRICAL_LIVE_LEARN_OUT_DIR:-artifacts/agent_modelica_electrical_live_learning_v0}"
BENCHMARK_PATH="${GATEFORGE_AGENT_ELECTRICAL_TASKS_PATH:-benchmarks/agent_modelica_electrical_tasks_v0.json}"
SCALES="${GATEFORGE_AGENT_ELECTRICAL_SCALES:-small,medium,large}"
MAX_TASKS="${GATEFORGE_AGENT_ELECTRICAL_MAX_TASKS:-0}"
FAILURE_CYCLE="${GATEFORGE_AGENT_ELECTRICAL_FAILURE_CYCLE:-model_check_error,simulate_error,semantic_regression}"
MUTATION_STYLE="${GATEFORGE_AGENT_ELECTRICAL_MUTATION_STYLE:-topology}"

MAX_ROUNDS="${GATEFORGE_AGENT_ELECTRICAL_MAX_ROUNDS:-2}"
MAX_TIME_SEC="${GATEFORGE_AGENT_ELECTRICAL_MAX_TIME_SEC:-180}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_ELECTRICAL_LIVE_TIMEOUT_SEC:-90}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_ELECTRICAL_LIVE_MAX_OUTPUT_CHARS:-2400}"

REPAIR_MEMORY_PATH="${GATEFORGE_AGENT_REPAIR_MEMORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"
PATCH_TEMPLATE_ADAPTATIONS_PATH="${GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH:-data/private_failure_corpus/agent_modelica_patch_template_adaptations_v1.json}"
RETRIEVAL_POLICY_PATH="${GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH:-data/private_failure_corpus/agent_modelica_retrieval_policy_v1.json}"

DEFAULT_LIVE_EXECUTOR_CMD="python3 -m gateforge.agent_modelica_live_executor_gemini_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${GATEFORGE_AGENT_LIVE_PLANNER_BACKEND:-gemini}\" --backend \"${GATEFORGE_AGENT_LIVE_OM_BACKEND:-auto}\" --docker-image \"${GATEFORGE_AGENT_LIVE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}\""
LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_LIVE_EXECUTOR_CMD:-$DEFAULT_LIVE_EXECUTOR_CMD}"

mkdir -p "$OUT_DIR"

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
  --repair-history "$REPAIR_MEMORY_PATH" \
  --patch-template-adaptations "$PATCH_TEMPLATE_ADAPTATIONS_PATH" \
  --retrieval-policy "$RETRIEVAL_POLICY_PATH" \
  --live-executor-cmd "$LIVE_EXECUTOR_CMD" \
  --live-timeout-sec "$LIVE_TIMEOUT_SEC" \
  --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS" \
  --results-out "$OUT_DIR/run_results.json" \
  --out "$OUT_DIR/run_summary.json"

python3 -m gateforge.agent_modelica_repair_memory_store_v1 \
  --run-results "$OUT_DIR/run_results.json" \
  --taskset "$OUT_DIR/taskset.json" \
  --memory "$REPAIR_MEMORY_PATH" \
  --include-failed \
  --out "$OUT_DIR/repair_memory_summary.json"

python3 -m gateforge.agent_modelica_repair_capability_learner_v1 \
  --repair-memory "$REPAIR_MEMORY_PATH" \
  --out-patch-template-adaptations "$PATCH_TEMPLATE_ADAPTATIONS_PATH" \
  --out-retrieval-policy "$RETRIEVAL_POLICY_PATH" \
  --out "$OUT_DIR/capability_learner_summary.json"

python3 -m gateforge.agent_modelica_diagnostic_quality_v0 \
  --run-results "$OUT_DIR/run_results.json" \
  --taskset "$OUT_DIR/taskset.json" \
  --out "$OUT_DIR/diagnostic_quality_summary.json"

export GATEFORGE_AGENT_ELECTRICAL_LIVE_LEARN_OUT_DIR="$OUT_DIR"
python3 - <<'PY'
import json
import os
from pathlib import Path

out_dir = Path(str(os.getenv("GATEFORGE_AGENT_ELECTRICAL_LIVE_LEARN_OUT_DIR") or "artifacts/agent_modelica_electrical_live_learning_v0"))
run_summary = {}
mem_summary = {}
learn_summary = {}
diag_summary = {}
for name, target in (
    ("run_summary", out_dir / "run_summary.json"),
    ("repair_memory_summary", out_dir / "repair_memory_summary.json"),
    ("capability_learner_summary", out_dir / "capability_learner_summary.json"),
    ("diagnostic_quality_summary", out_dir / "diagnostic_quality_summary.json"),
):
    if target.exists():
        payload = json.loads(target.read_text(encoding="utf-8"))
        if name == "run_summary":
            run_summary = payload
        elif name == "repair_memory_summary":
            mem_summary = payload
        elif name == "capability_learner_summary":
            learn_summary = payload
        else:
            diag_summary = payload
print(json.dumps({
    "status": "PASS",
    "run_status": run_summary.get("status"),
    "success_at_k_pct": run_summary.get("success_at_k_pct"),
    "repair_memory_total_rows": mem_summary.get("total_rows"),
    "learned_failure_type_count": learn_summary.get("learned_failure_type_count"),
    "diagnostic_parse_coverage_pct": diag_summary.get("parse_coverage_pct"),
    "diagnostic_type_match_rate_pct": diag_summary.get("type_match_rate_pct"),
    "diagnostic_stage_match_rate_pct": diag_summary.get("stage_match_rate_pct"),
}))
PY
