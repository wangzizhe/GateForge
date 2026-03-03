#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_MODELICA_MANIFEST_EXPAND_OUT_DIR:-artifacts/modelica_open_source_manifest_expand_v1}"
SOURCE_MANIFEST="${GATEFORGE_MODELICA_SOURCE_MANIFEST:-data/modelica_open_source_seed_sources_v1.json}"
CACHE_ROOT="${GATEFORGE_MODELICA_SOURCE_CACHE_ROOT:-assets_private/modelica_sources}"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

python3 -m gateforge.dataset_modelica_source_manifest_expander_v1 \
  --source-manifest "$SOURCE_MANIFEST" \
  --source-cache-root "$CACHE_ROOT" \
  --max-shards-per-source "${GATEFORGE_MANIFEST_EXPAND_MAX_SHARDS_PER_SOURCE:-6}" \
  --min-mo-files-per-shard "${GATEFORGE_MANIFEST_EXPAND_MIN_MO_FILES_PER_SHARD:-8}" \
  --out "$OUT_DIR/expanded_manifest.json" \
  --summary-out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

cat "$OUT_DIR/summary.json"
