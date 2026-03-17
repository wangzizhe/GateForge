#!/usr/bin/env bash
set -euo pipefail

export GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_RESUME=1

if [ -n "${GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_RESUME_RUN_ID:-}" ] && [ -z "${GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_RUN_ID:-}" ]; then
  export GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_RUN_ID="$GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_RESUME_RUN_ID"
fi

bash scripts/run_agent_modelica_behavioral_contract_live_evidence_v1.sh
