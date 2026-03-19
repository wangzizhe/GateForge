#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RESUME_RUN_ID="${GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_RESUME_RUN_ID:-}"
if [ -z "$RESUME_RUN_ID" ]; then
  echo "GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_RESUME_RUN_ID is required" >&2
  exit 1
fi

OUT_DIR="${GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_LIVE_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_behavioral_robustness_live_evidence_v1}"
export GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_RUN_ID="$RESUME_RUN_ID"
export GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_RUN_ROOT="${GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_RUN_ROOT:-$OUT_DIR/runs/$RESUME_RUN_ID}"
export GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_RESUME=1

bash scripts/run_agent_modelica_behavioral_robustness_live_evidence_v1.sh
