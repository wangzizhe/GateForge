#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_REAL_MODEL_MUTATION_MILESTONE_OUT_DIR:-artifacts/real_model_mutation_milestone_evidence_pack_v1}"
BOOTSTRAP_SUMMARY="${GATEFORGE_MODELICA_BOOTSTRAP_SUMMARY:-artifacts/modelica_open_source_bootstrap_v1/summary.json}"
SCALE_SUMMARY="${GATEFORGE_SCALE_BATCH_SUMMARY:-}"
SCALE_GATE_SUMMARY="${GATEFORGE_SCALE_GATE_SUMMARY:-}"
SOURCE_MANIFEST="${GATEFORGE_MODELICA_SOURCE_MANIFEST:-data/modelica_open_source_seed_sources_v1.json}"

if [ -z "$SCALE_SUMMARY" ]; then
  if [ -f "artifacts/private_model_mutation_scale_depth6_sprint_v1/summary.json" ]; then
    SCALE_SUMMARY="artifacts/private_model_mutation_scale_depth6_sprint_v1/summary.json"
  elif [ -f "artifacts/private_model_mutation_scale_depth4_sprint_v1/summary.json" ]; then
    SCALE_SUMMARY="artifacts/private_model_mutation_scale_depth4_sprint_v1/summary.json"
  else
    SCALE_SUMMARY="artifacts/private_model_mutation_scale_sprint_v1/summary.json"
  fi
fi

if [ -z "$SCALE_GATE_SUMMARY" ]; then
  if [ -f "artifacts/private_model_mutation_scale_depth6_sprint_v1/scale_gate_summary.json" ]; then
    SCALE_GATE_SUMMARY="artifacts/private_model_mutation_scale_depth6_sprint_v1/scale_gate_summary.json"
  elif [ -f "artifacts/private_model_mutation_scale_depth4_sprint_v1/scale_gate_summary.json" ]; then
    SCALE_GATE_SUMMARY="artifacts/private_model_mutation_scale_depth4_sprint_v1/scale_gate_summary.json"
  else
    SCALE_GATE_SUMMARY="artifacts/private_model_mutation_scale_sprint_v1/scale_gate_summary.json"
  fi
fi

mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

SCALE_DIR="$(cd "$(dirname "$SCALE_SUMMARY")" && pwd)"
UNIQUENESS_SUMMARY="$OUT_DIR/uniqueness_guard_summary.json"
python3 -m gateforge.dataset_real_model_uniqueness_guard_v1 \
  --intake-runner-accepted "$SCALE_DIR/intake_runner_accepted.json" \
  --intake-registry-rows "$SCALE_DIR/intake_registry_rows.json" \
  --out "$UNIQUENESS_SUMMARY" \
  --report-out "$OUT_DIR/uniqueness_guard_summary.md"

python3 -m gateforge.dataset_real_model_mutation_milestone_evidence_pack_v1 \
  --open-source-bootstrap-summary "$BOOTSTRAP_SUMMARY" \
  --scale-batch-summary "$SCALE_SUMMARY" \
  --scale-gate-summary "$SCALE_GATE_SUMMARY" \
  --uniqueness-guard-summary "$UNIQUENESS_SUMMARY" \
  --source-manifest "$SOURCE_MANIFEST" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

cat "$OUT_DIR/summary.json"
