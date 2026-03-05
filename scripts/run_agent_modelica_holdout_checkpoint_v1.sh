#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_HOLDOUT_CHECKPOINT_OUT_DIR:-artifacts/agent_modelica_holdout_checkpoint_v1}"
PROFILE_PATH="${GATEFORGE_AGENT_MVP_PROFILE_PATH:-benchmarks/agent_modelica_mvp_repair_v1.json}"
EXCLUDE_TASKSET="${GATEFORGE_AGENT_HOLDOUT_EXCLUDE_TASKSET:-}"
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

if [ -z "$CORE_MANIFEST" ] || [ -z "$SMALL_MANIFEST" ]; then
  echo "Missing manifests. Set GATEFORGE_AGENT_CORE_MUTATION_MANIFEST and GATEFORGE_AGENT_SMALL_MUTATION_MANIFEST." >&2
  exit 1
fi

PROFILE_MAX_ROUNDS=""
PROFILE_MAX_TIME_SEC=""
PROFILE_RUNTIME_THRESHOLD=""
PROFILE_SMALL_MAX_TIME_SEC=""
PROFILE_MEDIUM_MAX_TIME_SEC=""
PROFILE_LARGE_MAX_TIME_SEC=""
PROFILE_SMALL_MAX_ROUNDS=""
PROFILE_MEDIUM_MAX_ROUNDS=""
PROFILE_LARGE_MAX_ROUNDS=""
PROFILE_PER_SCALE_TOTAL=""
PROFILE_PER_SCALE_FAILURE_TARGETS=""
PROFILE_REPAIR_HISTORY_PATH=""

if [ -f "$PROFILE_PATH" ]; then
  eval "$(
    python3 - "$PROFILE_PATH" <<'PY'
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
pair_limit = None
if isinstance(per_ftype, dict) and per_ftype:
    nums = []
    for value in per_ftype.values():
        try:
            nums.append(int(value))
        except Exception:
            pass
    if nums:
        pair_limit = min(nums)

put("PROFILE_MAX_ROUNDS", get(payload, "run_contract.max_rounds"))
put("PROFILE_MAX_TIME_SEC", get(payload, "run_contract.max_time_sec"))
put("PROFILE_RUNTIME_THRESHOLD", get(payload, "run_contract.runtime_threshold"))
put("PROFILE_SMALL_MAX_TIME_SEC", get(payload, "acceptance_budgets.small_max_time_sec"))
put("PROFILE_MEDIUM_MAX_TIME_SEC", get(payload, "acceptance_budgets.medium_max_time_sec"))
put("PROFILE_LARGE_MAX_TIME_SEC", get(payload, "acceptance_budgets.large_max_time_sec"))
put("PROFILE_SMALL_MAX_ROUNDS", get(payload, "acceptance_budgets.small_max_rounds"))
put("PROFILE_MEDIUM_MAX_ROUNDS", get(payload, "acceptance_budgets.medium_max_rounds"))
put("PROFILE_LARGE_MAX_ROUNDS", get(payload, "acceptance_budgets.large_max_rounds"))
put("PROFILE_PER_SCALE_TOTAL", get(payload, "taskset.per_scale_total_target"))
put("PROFILE_PER_SCALE_FAILURE_TARGETS", pair_limit)
put("PROFILE_REPAIR_HISTORY_PATH", get(payload, "privacy.repair_history_path"))
PY
  )"
fi

MAX_ROUNDS="${GATEFORGE_AGENT_MAX_ROUNDS:-${PROFILE_MAX_ROUNDS:-9}}"
MAX_TIME_SEC="${GATEFORGE_AGENT_MAX_TIME_SEC:-${PROFILE_MAX_TIME_SEC:-1200}}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_RUNTIME_THRESHOLD:-${PROFILE_RUNTIME_THRESHOLD:-0.2}}"
SMALL_MAX_TIME_SEC="${GATEFORGE_AGENT_SMALL_MAX_TIME_SEC:-${PROFILE_SMALL_MAX_TIME_SEC:-180}}"
MEDIUM_MAX_TIME_SEC="${GATEFORGE_AGENT_MEDIUM_MAX_TIME_SEC:-${PROFILE_MEDIUM_MAX_TIME_SEC:-420}}"
LARGE_MAX_TIME_SEC="${GATEFORGE_AGENT_LARGE_MAX_TIME_SEC:-${PROFILE_LARGE_MAX_TIME_SEC:-900}}"
SMALL_MAX_ROUNDS="${GATEFORGE_AGENT_SMALL_MAX_ROUNDS:-${PROFILE_SMALL_MAX_ROUNDS:-3}}"
MEDIUM_MAX_ROUNDS="${GATEFORGE_AGENT_MEDIUM_MAX_ROUNDS:-${PROFILE_MEDIUM_MAX_ROUNDS:-6}}"
LARGE_MAX_ROUNDS="${GATEFORGE_AGENT_LARGE_MAX_ROUNDS:-${PROFILE_LARGE_MAX_ROUNDS:-9}}"
MAX_PER_SCALE="${GATEFORGE_AGENT_HOLDOUT_MAX_PER_SCALE:-${PROFILE_PER_SCALE_TOTAL:-12}}"
MAX_PER_SCALE_FAILURE="${GATEFORGE_AGENT_HOLDOUT_MAX_PER_SCALE_FAILURE_TYPE:-${PROFILE_PER_SCALE_FAILURE_TARGETS:-4}}"
REPAIR_HISTORY_PATH="${GATEFORGE_AGENT_REPAIR_HISTORY_PATH:-${PROFILE_REPAIR_HISTORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}}"

mkdir -p "$OUT_DIR"
HOLDOUT_TASKSET="$OUT_DIR/holdout_taskset.json"
HOLDOUT_TASKSET_SUMMARY="$OUT_DIR/holdout_taskset_summary.json"
HOLDOUT_BASELINE_OUT_DIR="$OUT_DIR/baseline"
HOLDOUT_SUMMARY="$OUT_DIR/summary.json"

HOLDOUT_BUILDER_CMD=(
  python3 -m gateforge.agent_modelica_holdout_taskset_builder_v1
  --mutation-manifest "$CORE_MANIFEST"
  --extra-mutation-manifest "$SMALL_MANIFEST"
  --max-per-scale "$MAX_PER_SCALE"
  --max-per-scale-failure-type "$MAX_PER_SCALE_FAILURE"
  --taskset-out "$HOLDOUT_TASKSET"
  --out "$HOLDOUT_TASKSET_SUMMARY"
  --report-out "$OUT_DIR/holdout_taskset_summary.md"
)
if [ -n "$EXCLUDE_TASKSET" ] && [ -f "$EXCLUDE_TASKSET" ]; then
  HOLDOUT_BUILDER_CMD+=(--exclude-taskset "$EXCLUDE_TASKSET")
fi
"${HOLDOUT_BUILDER_CMD[@]}"

python3 -m gateforge.agent_modelica_layered_baseline_v1 \
  --taskset-in "$HOLDOUT_TASKSET" \
  --run-mode evidence \
  --max-rounds "$MAX_ROUNDS" \
  --max-time-sec "$MAX_TIME_SEC" \
  --runtime-threshold "$RUNTIME_THRESHOLD" \
  --small-max-time-sec "$SMALL_MAX_TIME_SEC" \
  --medium-max-time-sec "$MEDIUM_MAX_TIME_SEC" \
  --large-max-time-sec "$LARGE_MAX_TIME_SEC" \
  --small-max-rounds "$SMALL_MAX_ROUNDS" \
  --medium-max-rounds "$MEDIUM_MAX_ROUNDS" \
  --large-max-rounds "$LARGE_MAX_ROUNDS" \
  --repair-history "$REPAIR_HISTORY_PATH" \
  --out-dir "$HOLDOUT_BASELINE_OUT_DIR" \
  --out "$HOLDOUT_SUMMARY" \
  --report-out "$OUT_DIR/summary.md"

cat "$HOLDOUT_SUMMARY"
