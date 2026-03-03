#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_REAL_MODEL_UNIQUENESS_OUT_DIR:-artifacts/real_model_uniqueness_guard_v1}"
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

python3 -m gateforge.dataset_real_model_uniqueness_guard_v1 \
  --intake-runner-accepted "$SCALE_DIR/intake_runner_accepted.json" \
  --intake-registry-rows "$SCALE_DIR/intake_registry_rows.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

cat "$OUT_DIR/summary.json"
