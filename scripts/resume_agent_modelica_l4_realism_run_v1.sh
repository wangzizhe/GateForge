#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_l4_realism_evidence_v1}"
RUN_ID="${GATEFORGE_AGENT_L4_REALISM_RESUME_RUN_ID:-${GATEFORGE_AGENT_L4_REALISM_RUN_ID:-}}"
RUN_ROOT="${GATEFORGE_AGENT_L4_REALISM_RESUME_RUN_ROOT:-${GATEFORGE_AGENT_L4_REALISM_RUN_ROOT:-}}"
STAGES="${GATEFORGE_AGENT_L4_REALISM_RESUME_STAGES:-auto}"
UPDATE_LATEST="${GATEFORGE_AGENT_L4_REALISM_UPDATE_LATEST:-1}"
FORCE_RERUN_COMPLETED="${GATEFORGE_AGENT_L4_REALISM_FORCE_RERUN_COMPLETED:-0}"

if [ "$#" -gt 0 ]; then
  python3 -m gateforge.agent_modelica_realism_run_lifecycle_v1 resume-run "$@"
else
  python3 -m gateforge.agent_modelica_realism_run_lifecycle_v1 resume-run \
    --out-dir "$OUT_DIR" \
    --run-id "$RUN_ID" \
    --run-root "$RUN_ROOT" \
    --stages "$STAGES" \
    --update-latest "$UPDATE_LATEST" \
    --force-rerun-completed "$FORCE_RERUN_COMPLETED"
fi
