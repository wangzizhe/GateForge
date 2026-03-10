#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_l4_realism_evidence_v1}"
RUN_ID="${GATEFORGE_AGENT_L4_REALISM_RUN_ID:-}"
RUN_ROOT="${GATEFORGE_AGENT_L4_REALISM_RUN_ROOT:-}"
INTERVAL_SEC="${GATEFORGE_AGENT_L4_REALISM_WATCH_INTERVAL_SEC:-30}"
LEGACY_ADOPT="${GATEFORGE_AGENT_L4_REALISM_LEGACY_ADOPT:-1}"
FINALIZE_ON_PROCESS_EXIT="${GATEFORGE_AGENT_L4_REALISM_FINALIZE_ON_PROCESS_EXIT:-1}"
UPDATE_LATEST="${GATEFORGE_AGENT_L4_REALISM_UPDATE_LATEST:-1}"
MAX_POLLS="${GATEFORGE_AGENT_L4_REALISM_WATCH_MAX_POLLS:-0}"

if [ "$#" -gt 0 ]; then
  python3 -m gateforge.agent_modelica_realism_run_lifecycle_v1 watch "$@"
else
  python3 -m gateforge.agent_modelica_realism_run_lifecycle_v1 watch \
    --out-dir "$OUT_DIR" \
    --run-id "$RUN_ID" \
    --run-root "$RUN_ROOT" \
    --interval-sec "$INTERVAL_SEC" \
    --legacy-adopt "$LEGACY_ADOPT" \
    --finalize-on-process-exit "$FINALIZE_ON_PROCESS_EXIT" \
    --update-latest "$UPDATE_LATEST" \
    --max-polls "$MAX_POLLS"
fi
