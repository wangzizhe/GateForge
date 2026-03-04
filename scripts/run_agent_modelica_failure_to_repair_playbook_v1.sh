#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_REPAIR_PLAYBOOK_OUT_DIR:-artifacts/agent_modelica_repair_playbook_v1}"
CORE_MANIFEST="${GATEFORGE_AGENT_CORE_MUTATION_MANIFEST:-artifacts/run_private_model_mutation_scale_batch_v1_demo/batch/mutation_manifest.json}"
SMALL_MANIFEST="${GATEFORGE_AGENT_SMALL_MUTATION_MANIFEST:-artifacts/run_modelica_open_source_growth_sprint_v1_demo/growth/scale/mutation_manifest.json}"
RUN_RESULTS="${GATEFORGE_AGENT_RUN_RESULTS:-artifacts/agent_modelica_layered_baseline_v1/run_results.json}"

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_failure_repair_corpus_v1 \
  --mutation-manifest "$CORE_MANIFEST" \
  --extra-mutation-manifest "$SMALL_MANIFEST" \
  --run-results "$RUN_RESULTS" \
  --out "$OUT_DIR/corpus.json" \
  --report-out "$OUT_DIR/corpus.md"

python3 -m gateforge.agent_modelica_repair_playbook_v1 \
  --corpus "$OUT_DIR/corpus.json" \
  --out "$OUT_DIR/playbook.json" \
  --report-out "$OUT_DIR/playbook.md"

cat "$OUT_DIR/playbook.json"
