#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RECIPE_LOCK_PATH="${GATEFORGE_AGENT_RECIPE_LOCK_PATH:-benchmarks/agent_modelica_mutant_recipe_lock_v1.json}"
OUT_DIR="${GATEFORGE_AGENT_RECIPE_LOCK_OUT_DIR:-artifacts/agent_modelica_mutant_recipe_lock_v1}"
SNAPSHOT_TAG="${GATEFORGE_AGENT_RECIPE_SNAPSHOT_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"

if [ ! -f "$RECIPE_LOCK_PATH" ]; then
  echo "recipe lock not found: $RECIPE_LOCK_PATH" >&2
  exit 1
fi

mkdir -p "$OUT_DIR/tasksets"

eval "$(
  python3 - "$RECIPE_LOCK_PATH" <<'PY'
import json
import shlex
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    lock = json.load(f)

taskset = lock.get("taskset") if isinstance(lock.get("taskset"), dict) else {}
source = str(taskset.get("source") or "").strip().lower()
hardpack_path = str(taskset.get("hardpack_path") or "").strip()
scales = taskset.get("scales")
failure_types = taskset.get("failure_types")
per_scale_total = taskset.get("per_scale_total_target")
targets = taskset.get("per_scale_failure_targets")

if isinstance(scales, list):
    scales = ",".join(str(x) for x in scales)
if isinstance(failure_types, list):
    failure_types = ",".join(str(x) for x in failure_types)
if isinstance(targets, dict) and isinstance(failure_types, str):
    order = [x.strip() for x in failure_types.split(",") if x.strip()]
    targets = ",".join(str(targets.get(k, 0)) for k in order)

def emit(name, value):
    if value is None:
        return
    print(f"{name}={shlex.quote(str(value))}")

emit("LOCK_SOURCE", source)
emit("LOCK_HARDPACK_PATH", hardpack_path)
emit("LOCK_SCALES", scales)
emit("LOCK_FAILURE_TYPES", failure_types)
emit("LOCK_PER_SCALE_TOTAL", per_scale_total)
emit("LOCK_PER_SCALE_FAILURE_TARGETS", targets)
PY
)"

TASKSET_PATH="$OUT_DIR/tasksets/taskset_${SNAPSHOT_TAG}.json"
SUMMARY_PATH="$OUT_DIR/tasksets/taskset_${SNAPSHOT_TAG}_summary.json"
LOCK_COPY_PATH="$OUT_DIR/tasksets/recipe_lock_${SNAPSHOT_TAG}.json"

cp "$RECIPE_LOCK_PATH" "$LOCK_COPY_PATH"

if [ "${LOCK_SOURCE:-}" = "hardpack" ]; then
  if [ -z "${LOCK_HARDPACK_PATH:-}" ]; then
    echo "recipe lock source=hardpack but hardpack_path is empty" >&2
    exit 1
  fi
  python3 -m gateforge.agent_modelica_hardpack_taskset_builder_v1 \
    --hardpack "$LOCK_HARDPACK_PATH" \
    --taskset-out "$TASKSET_PATH" \
    --out "$SUMMARY_PATH" \
    --report-out "${SUMMARY_PATH%.json}.md"
else
  if [ -z "${LOCK_HARDPACK_PATH:-}" ]; then
    echo "recipe lock currently requires hardpack_path for source=${LOCK_SOURCE:-unknown}" >&2
    exit 1
  fi
  python3 -m gateforge.agent_modelica_taskset_snapshot_v1 \
    --mutation-manifest "$LOCK_HARDPACK_PATH" \
    --scales "${LOCK_SCALES:-small,medium,large}" \
    --failure-types "${LOCK_FAILURE_TYPES:-model_check_error,simulate_error,semantic_regression}" \
    --per-scale-total "${LOCK_PER_SCALE_TOTAL:-12}" \
    --per-scale-failure-targets "${LOCK_PER_SCALE_FAILURE_TARGETS:-4,4,4}" \
    --snapshot-version "$SNAPSHOT_TAG" \
    --taskset-out "$TASKSET_PATH" \
    --out "$SUMMARY_PATH" \
    --report-out "${SUMMARY_PATH%.json}.md"
fi

python3 - "$RECIPE_LOCK_PATH" "$TASKSET_PATH" "$SUMMARY_PATH" "$LOCK_COPY_PATH" "$OUT_DIR/summary.json" "$SNAPSHOT_TAG" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

lock = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
taskset = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
taskset_summary = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
summary = {
    "schema_version": "agent_modelica_mutant_recipe_lock_v1_execution",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS" if isinstance(taskset.get("tasks"), list) and taskset.get("tasks") else "NEEDS_REVIEW",
    "recipe_id": lock.get("recipe_id"),
    "snapshot_tag": sys.argv[6],
    "task_count": len(taskset.get("tasks") or []),
    "paths": {
        "recipe_lock": sys.argv[1],
        "recipe_lock_copy": sys.argv[4],
        "taskset": sys.argv[2],
        "taskset_summary": sys.argv[3],
    },
}
Path(sys.argv[5]).write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary))
PY

cat "$OUT_DIR/summary.json"
