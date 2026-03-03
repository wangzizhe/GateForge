#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_COVERAGE_GATE_OUT_DIR:-artifacts/real_model_mutation_coverage_quality_gate_v1}"
SCALE_SUMMARY="${GATEFORGE_SCALE_BATCH_SUMMARY:-}"

if [ -z "$SCALE_SUMMARY" ]; then
  if [ -f "artifacts/private_model_mutation_scale_depth6_sprint_v1/summary.json" ]; then
    SCALE_SUMMARY="artifacts/private_model_mutation_scale_depth6_sprint_v1/summary.json"
  elif [ -f "artifacts/private_model_mutation_scale_depth4_sprint_v1/summary.json" ]; then
    SCALE_SUMMARY="artifacts/private_model_mutation_scale_depth4_sprint_v1/summary.json"
  else
    SCALE_SUMMARY="artifacts/private_model_mutation_scale_sprint_v1/summary.json"
  fi
fi

SCALE_DIR="$(cd "$(dirname "$SCALE_SUMMARY")" && pwd)"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

python3 -m gateforge.dataset_real_model_mutation_coverage_quality_gate_v1 \
  --real-model-registry "$SCALE_DIR/intake_registry_rows.json" \
  --validated-mutation-manifest "$SCALE_DIR/mutation_manifest.json" \
  --mutation-raw-observations "$SCALE_DIR/mutation_raw_observations.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

cat "$OUT_DIR/summary.json"
