#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

bash scripts/run_agent_modelica_v0_3_0_seal_v1.sh
bash scripts/run_agent_modelica_structural_singularity_trial_v0_3_1.sh
bash scripts/run_agent_modelica_layer4_holdout_v0_3_1.sh
bash scripts/run_agent_modelica_layer4_holdout_pack_v0_3_1.sh
bash scripts/run_agent_modelica_harder_holdout_ablation_v0_3_1.sh --planner-backend gemini
python3 -m gateforge.agent_modelica_external_agent_mcp_surface_v0_3_1 \
  --probe-summary artifacts/agent_modelica_external_agent_mcp_probe_v0_3_1_claude_trace3/summary.json \
  --probe-summary artifacts/agent_modelica_external_agent_mcp_probe_v0_3_1_codex_trace3/summary.json
python3 -m gateforge.agent_modelica_v0_3_1_release_summary
