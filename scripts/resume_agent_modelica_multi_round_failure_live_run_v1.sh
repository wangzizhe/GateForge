#!/usr/bin/env bash
set -euo pipefail

export GATEFORGE_AGENT_MULTI_ROUND_FAILURE_RESUME=1

if [ -n "${GATEFORGE_AGENT_MULTI_ROUND_FAILURE_RESUME_RUN_ID:-}" ] && [ -z "${GATEFORGE_AGENT_MULTI_ROUND_FAILURE_RUN_ID:-}" ]; then
  export GATEFORGE_AGENT_MULTI_ROUND_FAILURE_RUN_ID="$GATEFORGE_AGENT_MULTI_ROUND_FAILURE_RESUME_RUN_ID"
fi

bash scripts/run_agent_modelica_multi_round_failure_live_evidence_v1.sh
