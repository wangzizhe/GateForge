#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_LANDSCAPE_OUT_DIR:-artifacts/agent_modelica_landscape_snapshot_v1}"
WEEKLY_DIR="${GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR:-artifacts/agent_modelica_weekly_chain_v1}"
TWO_WEEK_DIR="${GATEFORGE_AGENT_TWO_WEEK_REPLAY_OUT_DIR:-artifacts/agent_modelica_two_week_replay_v1}"
DEFAULT_HARDPACK_PATH="benchmarks/agent_modelica_hardpack_v1.json"
if [ -f "benchmarks/private/agent_modelica_hardpack_v1.json" ]; then
  DEFAULT_HARDPACK_PATH="benchmarks/private/agent_modelica_hardpack_v1.json"
fi
HARDPACK_PATH="${GATEFORGE_AGENT_HARDPACK_PATH:-$DEFAULT_HARDPACK_PATH}"

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_landscape_snapshot_v1 \
  --weekly-summary "$WEEKLY_DIR/summary.json" \
  --weekly-decision "$WEEKLY_DIR/weekly/decision.json" \
  --two-week-summary "$TWO_WEEK_DIR/summary.json" \
  --hardpack "$HARDPACK_PATH" \
  --out "$OUT_DIR/snapshot.json" \
  --report-out "$OUT_DIR/snapshot.md"

cat "$OUT_DIR/snapshot.json"
