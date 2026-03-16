#!/usr/bin/env bash
set -euo pipefail

export GATEFORGE_AGENT_WAVE2_REALISM_RESUME=1
export GATEFORGE_AGENT_WAVE2_REALISM_RUN_ID="${GATEFORGE_AGENT_WAVE2_REALISM_RESUME_RUN_ID:-${GATEFORGE_AGENT_WAVE2_REALISM_RUN_ID:-}}"

bash scripts/run_agent_modelica_wave2_realism_live_evidence_v1.sh
