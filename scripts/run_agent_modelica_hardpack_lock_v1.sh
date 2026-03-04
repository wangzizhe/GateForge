#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_PATH="${GATEFORGE_AGENT_HARDPACK_OUT:-benchmarks/agent_modelica_hardpack_v1.json}"
VERSION="${GATEFORGE_AGENT_HARDPACK_VERSION:-agent_modelica_hardpack_v1}"
PER_SCALE_TOTAL="${GATEFORGE_AGENT_HARDPACK_PER_SCALE_TOTAL:-12}"
PER_SCALE_FAILURE_TARGETS="${GATEFORGE_AGENT_HARDPACK_PER_SCALE_FAILURE_TARGETS:-4,4,4}"
CORE_MANIFEST="${GATEFORGE_AGENT_CORE_MUTATION_MANIFEST:-artifacts/run_private_model_mutation_scale_batch_v1_demo/batch/mutation_manifest.json}"
SMALL_MANIFEST="${GATEFORGE_AGENT_SMALL_MUTATION_MANIFEST:-artifacts/run_modelica_open_source_growth_sprint_v1_demo/growth/scale/mutation_manifest.json}"

if [ ! -f "$CORE_MANIFEST" ] || [ ! -f "$SMALL_MANIFEST" ]; then
  echo "Missing mutation manifests for hardpack lock." >&2
  echo "Set GATEFORGE_AGENT_CORE_MUTATION_MANIFEST and GATEFORGE_AGENT_SMALL_MUTATION_MANIFEST." >&2
  exit 1
fi

python3 -m gateforge.agent_modelica_hardpack_lock_v1 \
  --mutation-manifest "$CORE_MANIFEST" \
  --extra-mutation-manifest "$SMALL_MANIFEST" \
  --hardpack-version "$VERSION" \
  --per-scale-total "$PER_SCALE_TOTAL" \
  --per-scale-failure-targets "$PER_SCALE_FAILURE_TARGETS" \
  --out "$OUT_PATH" \
  --report-out "${OUT_PATH%.json}.md"

cat "$OUT_PATH"
