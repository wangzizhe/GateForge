#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_ELECTRICAL_REALISM_OUT_DIR:-artifacts/agent_modelica_electrical_realism_frozen_taskset_v1}"
BENCHMARK_PATH="${GATEFORGE_AGENT_ELECTRICAL_REALISM_TASKS_PATH:-benchmarks/agent_modelica_electrical_tasks_v0.json}"
SCALES="${GATEFORGE_AGENT_ELECTRICAL_REALISM_SCALES:-small,medium}"
MAX_TASKS="${GATEFORGE_AGENT_ELECTRICAL_REALISM_MAX_TASKS:-0}"
FAILURE_TYPES="${GATEFORGE_AGENT_ELECTRICAL_REALISM_FAILURE_TYPES:-underconstrained_system,connector_mismatch,initialization_infeasible}"
REQUIRED_CATEGORIES="${GATEFORGE_AGENT_ELECTRICAL_REALISM_REQUIRED_CATEGORIES:-topology_wiring,initialization}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_ELECTRICAL_REALISM_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_ELECTRICAL_REALISM_SPLIT_SEED:-agent_modelica_electrical_realism_v1}"
PACK_ID="${GATEFORGE_AGENT_ELECTRICAL_REALISM_PACK_ID:-agent_modelica_realism_pack_v1}"
PACK_VERSION="${GATEFORGE_AGENT_ELECTRICAL_REALISM_PACK_VERSION:-v1}"
PACK_TRACK="${GATEFORGE_AGENT_ELECTRICAL_REALISM_PACK_TRACK:-realism}"
ACCEPTANCE_SCOPE="${GATEFORGE_AGENT_ELECTRICAL_REALISM_ACCEPTANCE_SCOPE:-independent_validation}"
BUILDER_SOURCE_PATH="$ROOT_DIR/gateforge/agent_modelica_electrical_mutant_taskset_v0.py"

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_electrical_mutant_taskset_v0 \
  --benchmark "$BENCHMARK_PATH" \
  --scales "$SCALES" \
  --max-tasks "$MAX_TASKS" \
  --failure-types "$FAILURE_TYPES" \
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

python3 - "$OUT_DIR" "$FAILURE_TYPES" "$REQUIRED_CATEGORIES" "$PACK_ID" "$PACK_VERSION" "$PACK_TRACK" "$ACCEPTANCE_SCOPE" "$BENCHMARK_PATH" "$SCALES" "$HOLDOUT_RATIO" "$SPLIT_SEED" "$BUILDER_SOURCE_PATH" <<'PY'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out_dir = Path(sys.argv[1])
failure_types = [x.strip().lower() for x in str(sys.argv[2] or "").split(",") if x.strip()]
required_categories = [x.strip().lower() for x in str(sys.argv[3] or "").split(",") if x.strip()]
pack_id = str(sys.argv[4] or "")
pack_version = str(sys.argv[5] or "")
pack_track = str(sys.argv[6] or "")
acceptance_scope = str(sys.argv[7] or "")
benchmark_path = str(sys.argv[8] or "")
scales = [x.strip().lower() for x in str(sys.argv[9] or "").split(",") if x.strip()]
holdout_ratio = float(sys.argv[10] or 0.15)
split_seed = str(sys.argv[11] or "")
builder_source_path = Path(sys.argv[12])
builder_source_sha = ""
if builder_source_path.exists():
    builder_source_sha = hashlib.sha256(builder_source_path.read_bytes()).hexdigest()

taskset = json.loads((out_dir / "taskset_frozen.json").read_text(encoding="utf-8"))
tasks = [x for x in (taskset.get("tasks") or []) if isinstance(x, dict)]
counts_by_scale = {}
counts_by_failure = {x: 0 for x in failure_types}
counts_by_category = {x: 0 for x in required_categories}
split_counts = {"train": 0, "holdout": 0}
for row in tasks:
    scale = str(row.get("scale") or "").strip().lower()
    failure = str(row.get("failure_type") or "").strip().lower()
    category = str(row.get("category") or "").strip().lower()
    split = str(row.get("split") or "train").strip().lower()
    counts_by_scale[scale] = int(counts_by_scale.get(scale, 0)) + 1
    counts_by_failure[failure] = int(counts_by_failure.get(failure, 0)) + 1
    if category:
        counts_by_category[category] = int(counts_by_category.get(category, 0)) + 1
    if split in split_counts:
        split_counts[split] += 1

missing_failure_types = [x for x in failure_types if int(counts_by_failure.get(x, 0)) <= 0]
missing_categories = [x for x in required_categories if int(counts_by_category.get(x, 0)) <= 0]
reasons = [f"requested_failure_type_missing:{x}" for x in missing_failure_types]
reasons.extend([f"required_category_missing:{x}" for x in missing_categories])
status = "PASS" if not reasons and tasks else "FAIL"

manifest = {
    "schema_version": "agent_modelica_electrical_realism_frozen_taskset_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "pack_id": pack_id,
    "pack_version": pack_version,
    "pack_track": pack_track,
    "acceptance_scope": acceptance_scope,
    "builder_provenance": {
        "builder_source_path": str(builder_source_path),
        "builder_source_sha": builder_source_sha,
    },
    "benchmark_path": benchmark_path,
    "scales": scales,
    "requested_failure_types": failure_types,
    "required_categories": required_categories,
    "holdout_ratio": holdout_ratio,
    "split_seed": split_seed,
    "counts": {
        "total_tasks": len(tasks),
        "counts_by_scale": counts_by_scale,
        "counts_by_failure_type": counts_by_failure,
        "counts_by_category": counts_by_category,
        "split_counts": split_counts,
    },
    "files": {
        "taskset_unfrozen": str(out_dir / "taskset_unfrozen.json"),
        "taskset_frozen": str(out_dir / "taskset_frozen.json"),
        "unfrozen_summary": str(out_dir / "unfrozen_summary.json"),
        "frozen_summary": str(out_dir / "frozen_summary.json"),
    },
    "reasons": reasons,
}

sha_payload = {
    "schema_version": "agent_modelica_electrical_realism_frozen_taskset_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "taskset_unfrozen": hashlib.sha256((out_dir / "taskset_unfrozen.json").read_bytes()).hexdigest(),
    "taskset_frozen": hashlib.sha256((out_dir / "taskset_frozen.json").read_bytes()).hexdigest(),
    "manifest": "",
}
(out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
sha_payload["manifest"] = hashlib.sha256((out_dir / "manifest.json").read_bytes()).hexdigest()
(out_dir / "sha256.json").write_text(json.dumps(sha_payload, indent=2), encoding="utf-8")

summary = {
    "schema_version": "agent_modelica_electrical_realism_frozen_taskset_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "pack_id": pack_id,
    "pack_version": pack_version,
    "pack_track": pack_track,
    "acceptance_scope": acceptance_scope,
    "builder_source_path": str(builder_source_path),
    "builder_source_sha": builder_source_sha,
    "total_tasks": len(tasks),
    "counts_by_scale": counts_by_scale,
    "counts_by_failure_type": counts_by_failure,
    "counts_by_category": counts_by_category,
    "split_counts": split_counts,
    "taskset_path": str(out_dir / "taskset_frozen.json"),
    "manifest_path": str(out_dir / "manifest.json"),
    "reasons": reasons,
}
(out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary))
if status != "PASS":
    raise SystemExit(1)
PY
