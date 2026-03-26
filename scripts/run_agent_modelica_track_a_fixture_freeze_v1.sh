#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DEFAULT_HARDPACK_PATH="benchmarks/agent_modelica_hardpack_v1.json"
if [ -f "benchmarks/private/agent_modelica_hardpack_v1.json" ]; then
  DEFAULT_HARDPACK_PATH="benchmarks/private/agent_modelica_hardpack_v1.json"
fi

HARDPACK_PATH="${GATEFORGE_AGENT_TRACK_A_SOURCE_HARDPACK:-$DEFAULT_HARDPACK_PATH}"
OUT_ROOT="${GATEFORGE_AGENT_TRACK_A_FIXTURE_ROOT:-assets_private/agent_modelica_track_a_valid32_fixture_v1}"

python3 -m gateforge.agent_modelica_benchmark_fixture_freeze_v1 \
  --hardpack "$HARDPACK_PATH" \
  --out-root "$OUT_ROOT" \
  --valid-only

cat "$OUT_ROOT/frozen_summary.json"
