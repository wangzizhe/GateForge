#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_V034_RULEPRIO_OUT_DIR:-artifacts/agent_modelica_v0_3_4_single_case_ruleprio_local}"
mkdir -p "$OUT_DIR"

TASK_ID="multi_round_ibpsa_acsimplegrid_coupled_conflict_failure_v034_ruleprio"
SOURCE_MODEL_PATH="$ROOT_DIR/artifacts/agent_modelica_multi_round_failure_taskset_v1_devcheck/source_models/ibpsa/acsimplegrid.mo"
MUTATED_MODEL_PATH="$ROOT_DIR/artifacts/agent_modelica_multi_round_failure_taskset_v1_devcheck/mutants/coupled_conflict_failure/ibpsa_acsimplegrid_coupled_conflict_failure.mo"
SOURCE_LIBRARY_PATH="$ROOT_DIR/assets_private/modelica_sources/modelica_ibpsa/IBPSA"
SOURCE_LIBRARY_MODEL_PATH="$ROOT_DIR/assets_private/modelica_sources/modelica_ibpsa/IBPSA/Electrical/AC/ThreePhasesUnbalanced/Lines/Examples/ACSimpleGrid.mo"
OUT_PATH="$OUT_DIR/ibpsa_acsimplegrid_coupled_conflict_failure.json"

env \
  GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR=1 \
  python3 -m gateforge.agent_modelica_live_executor_gemini_v1 \
    --task-id "$TASK_ID" \
    --failure-type coupled_conflict_failure \
    --expected-stage simulate \
    --source-model-path "$SOURCE_MODEL_PATH" \
    --mutated-model-path "$MUTATED_MODEL_PATH" \
    --source-library-path "$SOURCE_LIBRARY_PATH" \
    --source-package-name IBPSA \
    --source-library-model-path "$SOURCE_LIBRARY_MODEL_PATH" \
    --source-qualified-model-name IBPSA.Electrical.AC.ThreePhasesUnbalanced.Lines.Examples.ACSimpleGrid \
    --backend openmodelica_docker \
    --planner-backend gemini \
    --max-rounds 3 \
    --timeout-sec 180 \
    --out "$OUT_PATH"

printf 'wrote %s\n' "$OUT_PATH"
