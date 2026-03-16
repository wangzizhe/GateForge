#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_LIVE_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_wave2_1_harder_dynamics_live_evidence_v1}"
RUN_ID="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_RESUME_RUN_ID:-}"

if [ -z "$RUN_ID" ]; then
  echo "GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_RESUME_RUN_ID is required" >&2
  exit 2
fi

export GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_RUN_ID="$RUN_ID"
export GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_RUN_ROOT="$OUT_DIR/runs/$RUN_ID"
export GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_RESUME=1

bash scripts/run_agent_modelica_wave2_1_harder_dynamics_live_evidence_v1.sh
