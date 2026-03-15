#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_TASKSET_OUT_DIR:-artifacts/agent_modelica_unknown_library_taskset_v1}"
MANIFEST_PATH="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_MANIFEST:-assets_private/agent_modelica_unknown_library_pool_v1/manifest.json}"
FAILURE_TYPES="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_FAILURE_TYPES:-underconstrained_system,connector_mismatch,initialization_infeasible}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_SPLIT_SEED:-agent_modelica_unknown_library_taskset_v1}"

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_unknown_library_taskset_v1 \
  --manifest "$MANIFEST_PATH" \
  --out-dir "$OUT_DIR" \
  --failure-types "$FAILURE_TYPES" \
  --holdout-ratio "$HOLDOUT_RATIO" \
  --seed "$SPLIT_SEED"

