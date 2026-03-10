#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_l4_realism_evidence_v1}"
RUN_ID="${GATEFORGE_AGENT_L4_REALISM_RUN_ID:-}"
RUN_ROOT="${GATEFORGE_AGENT_L4_REALISM_RUN_ROOT:-}"
UPDATE_FINAL_SUMMARY="${GATEFORGE_AGENT_L4_REALISM_REPAIR_QUEUE_UPDATE_FINAL_SUMMARY:-1}"

if [ "$#" -gt 0 ]; then
  python3 -m gateforge.agent_modelica_realism_repair_queue_v1 "$@"
else
  python3 -m gateforge.agent_modelica_realism_repair_queue_v1 \
    --out-dir "$OUT_DIR" \
    --run-id "$RUN_ID" \
    --run-root "$RUN_ROOT" \
    --update-final-summary "$UPDATE_FINAL_SUMMARY"
fi
