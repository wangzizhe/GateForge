#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_LONGHAUL_OUT_DIR:-artifacts/agent_modelica_longhaul_v0}"
TOTAL_MINUTES="${GATEFORGE_AGENT_LONGHAUL_TOTAL_MINUTES:-240}"
SEGMENT_TIMEOUT_SEC="${GATEFORGE_AGENT_LONGHAUL_SEGMENT_TIMEOUT_SEC:-1200}"
MAX_SEGMENTS="${GATEFORGE_AGENT_LONGHAUL_MAX_SEGMENTS:-0}"
RETRY_PER_SEGMENT="${GATEFORGE_AGENT_LONGHAUL_RETRY_PER_SEGMENT:-0}"
CONTINUE_ON_FAIL="${GATEFORGE_AGENT_LONGHAUL_CONTINUE_ON_FAIL:-1}"
SLEEP_BETWEEN_SEC="${GATEFORGE_AGENT_LONGHAUL_SLEEP_BETWEEN_SEC:-2}"
RESUME="${GATEFORGE_AGENT_LONGHAUL_RESUME:-1}"
WORKDIR="${GATEFORGE_AGENT_LONGHAUL_CWD:-$ROOT_DIR}"

DEFAULT_SEGMENT_COMMAND='GATEFORGE_AGENT_L4_UPLIFT_OUT_DIR="$GATEFORGE_AGENT_LONGHAUL_SEGMENT_OUT_DIR" bash scripts/run_agent_modelica_l4_uplift_evidence_v0.sh'
SEGMENT_COMMAND="${GATEFORGE_AGENT_LONGHAUL_SEGMENT_COMMAND:-$DEFAULT_SEGMENT_COMMAND}"

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_longhaul_v0 \
  --command "$SEGMENT_COMMAND" \
  --cwd "$WORKDIR" \
  --out-dir "$OUT_DIR" \
  --total-minutes "$TOTAL_MINUTES" \
  --segment-timeout-sec "$SEGMENT_TIMEOUT_SEC" \
  --max-segments "$MAX_SEGMENTS" \
  --retry-per-segment "$RETRY_PER_SEGMENT" \
  --continue-on-fail "$CONTINUE_ON_FAIL" \
  --sleep-between-sec "$SLEEP_BETWEEN_SEC" \
  --resume "$RESUME" \
  --summary-out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md" \
  --state-out "$OUT_DIR/state.json"

cat "$OUT_DIR/summary.json"
