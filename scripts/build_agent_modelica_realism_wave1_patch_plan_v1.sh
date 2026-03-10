#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_l4_realism_evidence_v1}"
RUN_ID="${GATEFORGE_AGENT_L4_REALISM_RUN_ID:-}"
RUN_ROOT="${GATEFORGE_AGENT_L4_REALISM_RUN_ROOT:-}"
PLAYBOOK_PATH="${GATEFORGE_AGENT_REALISM_WAVE1_PATCH_PLAYBOOK:-}"
UPDATE_FINAL_SUMMARY="${GATEFORGE_AGENT_REALISM_WAVE1_PATCH_UPDATE_FINAL_SUMMARY:-1}"

python3 -m gateforge.agent_modelica_realism_wave1_patch_plan_v1 \
  --out-dir "$OUT_DIR" \
  --run-id "$RUN_ID" \
  --run-root "$RUN_ROOT" \
  --playbook "$PLAYBOOK_PATH" \
  --update-final-summary "$UPDATE_FINAL_SUMMARY"
