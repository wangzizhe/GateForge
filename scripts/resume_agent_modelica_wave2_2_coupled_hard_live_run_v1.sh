#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_WAVE2_2_COUPLED_HARD_LIVE_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_wave2_2_coupled_hard_live_evidence_v1}"
RUN_ID="${GATEFORGE_AGENT_WAVE2_2_COUPLED_HARD_RESUME_RUN_ID:?GATEFORGE_AGENT_WAVE2_2_COUPLED_HARD_RESUME_RUN_ID is required}"
export GATEFORGE_AGENT_WAVE2_2_COUPLED_HARD_RUN_ID="$RUN_ID"
export GATEFORGE_AGENT_WAVE2_2_COUPLED_HARD_RUN_ROOT="${GATEFORGE_AGENT_WAVE2_2_COUPLED_HARD_RUN_ROOT:-$OUT_DIR/runs/$RUN_ID}"
export GATEFORGE_AGENT_WAVE2_2_COUPLED_HARD_RESUME=1

bash scripts/run_agent_modelica_wave2_2_coupled_hard_live_evidence_v1.sh
