#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L2_FREEZE_PACK_OUT_DIR:-assets_private/agent_modelica_l2_freeze_pack_v0}"
BENCHMARK_PATH="${GATEFORGE_AGENT_ELECTRICAL_TASKS_PATH:-benchmarks/agent_modelica_electrical_tasks_v0.json}"
SCALES="${GATEFORGE_AGENT_L2_FREEZE_SCALES:-small,medium}"
MAX_TASKS="${GATEFORGE_AGENT_L2_FREEZE_MAX_TASKS:-0}"
FAILURE_TYPES="${GATEFORGE_AGENT_L2_FREEZE_FAILURE_TYPES:-model_check_error,simulate_error,semantic_regression}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_L2_FREEZE_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_L2_FREEZE_SPLIT_SEED:-agent_modelica_l2_electrical_v0}"

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
  --out "$OUT_DIR/unfrozen_summary.json" \
  --report-out "$OUT_DIR/unfrozen_summary.md"

python3 -m gateforge.agent_modelica_taskset_split_freeze_v1 \
  --taskset-in "$OUT_DIR/taskset_unfrozen.json" \
  --holdout-ratio "$HOLDOUT_RATIO" \
  --seed "$SPLIT_SEED" \
  --out-taskset "$OUT_DIR/taskset_frozen.json" \
  --out "$OUT_DIR/frozen_summary.json" \
  --report-out "$OUT_DIR/frozen_summary.md"

export GATEFORGE_AGENT_L2_FREEZE_OUT_DIR="$OUT_DIR"
export GATEFORGE_AGENT_L2_FREEZE_BENCHMARK="$BENCHMARK_PATH"
export GATEFORGE_AGENT_L2_FREEZE_SCALES="$SCALES"
export GATEFORGE_AGENT_L2_FREEZE_FAILURE_TYPES="$FAILURE_TYPES"
export GATEFORGE_AGENT_L2_FREEZE_HOLDOUT_RATIO="$HOLDOUT_RATIO"
export GATEFORGE_AGENT_L2_FREEZE_SPLIT_SEED="$SPLIT_SEED"
python3 - <<'PY'
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

out_dir = Path(os.environ["GATEFORGE_AGENT_L2_FREEZE_OUT_DIR"])
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

def sha(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

manifest = {
    "schema_version": "agent_modelica_l2_freeze_pack_v0",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS",
    "benchmark_path": os.environ["GATEFORGE_AGENT_L2_FREEZE_BENCHMARK"],
    "scales": [x for x in os.environ["GATEFORGE_AGENT_L2_FREEZE_SCALES"].split(",") if x],
    "failure_types": [x for x in os.environ["GATEFORGE_AGENT_L2_FREEZE_FAILURE_TYPES"].split(",") if x],
    "holdout_ratio": float(os.environ["GATEFORGE_AGENT_L2_FREEZE_HOLDOUT_RATIO"]),
    "split_seed": os.environ["GATEFORGE_AGENT_L2_FREEZE_SPLIT_SEED"],
    "total_tasks": len(tasks),
    "counts_by_scale": counts_by_scale,
    "counts_by_failure_type": counts_by_failure,
    "split_counts": split_counts,
    "files": {
        "taskset_unfrozen": str(out_dir / "taskset_unfrozen.json"),
        "taskset_frozen": str(out_dir / "taskset_frozen.json"),
    },
    "sha256": {
        "taskset_unfrozen": sha(out_dir / "taskset_unfrozen.json"),
        "taskset_frozen": sha(out_dir / "taskset_frozen.json"),
    },
}
(out_dir / "freeze_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
(out_dir / "freeze_manifest.md").write_text(
    "\n".join(
        [
            "# Agent Modelica L2 Freeze Pack v0",
            "",
            f"- status: `{manifest['status']}`",
            f"- total_tasks: `{manifest['total_tasks']}`",
            f"- split_seed: `{manifest['split_seed']}`",
            f"- holdout_ratio: `{manifest['holdout_ratio']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"status": "PASS", "total_tasks": len(tasks)}))
PY

cat "$OUT_DIR/freeze_manifest.json"
