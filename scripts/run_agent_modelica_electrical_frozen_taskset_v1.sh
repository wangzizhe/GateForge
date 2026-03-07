#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_ELECTRICAL_FROZEN_OUT_DIR:-artifacts/agent_modelica_electrical_frozen_taskset_v1}"
BENCHMARK_PATH="${GATEFORGE_AGENT_ELECTRICAL_TASKS_PATH:-benchmarks/agent_modelica_electrical_tasks_v0.json}"
SCALES="${GATEFORGE_AGENT_ELECTRICAL_SCALES:-small,medium,large}"
MAX_TASKS="${GATEFORGE_AGENT_ELECTRICAL_MAX_TASKS:-0}"
FAILURE_TYPES="${GATEFORGE_AGENT_ELECTRICAL_FAILURE_TYPES:-model_check_error,simulate_error,semantic_regression}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_ELECTRICAL_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_ELECTRICAL_SPLIT_SEED:-agent_modelica_electrical_frozen_v1}"

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_electrical_mutant_taskset_v0 \
  --benchmark "$BENCHMARK_PATH" \
  --scales "$SCALES" \
  --max-tasks "$MAX_TASKS" \
  --failure-cycle "$FAILURE_TYPES" \
  --expand-failure-types \
  --source-models-dir "$OUT_DIR/source_models" \
  --mutants-dir "$OUT_DIR/mutants" \
  --taskset-out "$OUT_DIR/taskset_unfrozen.json" \
  --out "$OUT_DIR/unfrozen_summary.json"

python3 -m gateforge.agent_modelica_taskset_split_freeze_v1 \
  --taskset-in "$OUT_DIR/taskset_unfrozen.json" \
  --holdout-ratio "$HOLDOUT_RATIO" \
  --seed "$SPLIT_SEED" \
  --out-taskset "$OUT_DIR/taskset_frozen.json" \
  --out "$OUT_DIR/frozen_summary.json"

export GATEFORGE_AGENT_ELECTRICAL_FROZEN_OUT_DIR="$OUT_DIR"
python3 - <<'PY'
import json
import os
from pathlib import Path

out_dir = Path(str(os.getenv("GATEFORGE_AGENT_ELECTRICAL_FROZEN_OUT_DIR") or "artifacts/agent_modelica_electrical_frozen_taskset_v1"))
taskset = json.loads((out_dir / "taskset_frozen.json").read_text(encoding="utf-8"))
tasks = [x for x in (taskset.get("tasks") or []) if isinstance(x, dict)]
counts_by_scale = {}
counts_by_failure = {}
split_counts = {"train": 0, "holdout": 0}
for row in tasks:
    scale = str(row.get("scale") or "")
    failure = str(row.get("failure_type") or "")
    split = str(row.get("split") or "train").lower()
    counts_by_scale[scale] = int(counts_by_scale.get(scale, 0)) + 1
    counts_by_failure[failure] = int(counts_by_failure.get(failure, 0)) + 1
    if split in split_counts:
        split_counts[split] += 1
summary = {
    "status": "PASS",
    "total_tasks": len(tasks),
    "counts_by_scale": counts_by_scale,
    "counts_by_failure_type": counts_by_failure,
    "split_counts": split_counts,
    "taskset_path": str((out_dir / "taskset_frozen.json")),
}
print(json.dumps(summary))
PY
