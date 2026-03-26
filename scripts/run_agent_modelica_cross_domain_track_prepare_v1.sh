#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TRACK_ID="${GATEFORGE_AGENT_CROSS_DOMAIN_TRACK_ID:-buildings_v1}"
SOURCE_MANIFEST="${GATEFORGE_AGENT_CROSS_DOMAIN_SOURCE_MANIFEST:-data/modelica_cross_domain_seed_sources_v1.json}"
TRACK_MANIFEST="${GATEFORGE_AGENT_CROSS_DOMAIN_TRACK_MANIFEST:-data/agent_modelica_cross_domain_track_manifest_v1.json}"
OUT_DIR="${GATEFORGE_AGENT_CROSS_DOMAIN_OUT_DIR:-artifacts/agent_modelica_cross_domain_track_prepare_v1/$TRACK_ID}"
FROZEN_ROOT="${GATEFORGE_AGENT_CROSS_DOMAIN_FROZEN_ROOT:-assets_private/agent_modelica_cross_domain_${TRACK_ID}_fixture_v1}"
TARGET_SCALES="${GATEFORGE_AGENT_CROSS_DOMAIN_TARGET_SCALES:-small,medium,large}"
FAILURE_TYPES="${GATEFORGE_AGENT_CROSS_DOMAIN_FAILURE_TYPES:-model_check_error,simulate_error,semantic_regression}"
MUTATIONS_PER_FAILURE_TYPE="${GATEFORGE_AGENT_CROSS_DOMAIN_MUTATIONS_PER_FAILURE_TYPE:-2}"
MAX_MODELS="${GATEFORGE_AGENT_CROSS_DOMAIN_MAX_MODELS:-6}"
PER_SCALE_TOTAL="${GATEFORGE_AGENT_CROSS_DOMAIN_PER_SCALE_TOTAL:-6}"
PER_SCALE_FAILURE_TARGETS="${GATEFORGE_AGENT_CROSS_DOMAIN_PER_SCALE_FAILURE_TARGETS:-2,2,2}"
VALID_ONLY="${GATEFORGE_AGENT_CROSS_DOMAIN_VALID_ONLY:-1}"
DRY_RUN="${GATEFORGE_AGENT_CROSS_DOMAIN_DRY_RUN:-0}"

ARGS=(
  --track-id "$TRACK_ID"
  --source-manifest "$SOURCE_MANIFEST"
  --track-manifest "$TRACK_MANIFEST"
  --out-dir "$OUT_DIR"
  --frozen-root "$FROZEN_ROOT"
  --target-scales "$TARGET_SCALES"
  --failure-types "$FAILURE_TYPES"
  --mutations-per-failure-type "$MUTATIONS_PER_FAILURE_TYPE"
  --max-models "$MAX_MODELS"
  --per-scale-total "$PER_SCALE_TOTAL"
  --per-scale-failure-targets "$PER_SCALE_FAILURE_TARGETS"
)

if [ "$VALID_ONLY" = "1" ]; then
  ARGS+=(--valid-only)
fi
if [ "$DRY_RUN" = "1" ]; then
  ARGS+=(--dry-run)
fi

python3 -m gateforge.agent_modelica_cross_domain_track_prepare_v1 "${ARGS[@]}"
cat "$OUT_DIR/summary.json"
