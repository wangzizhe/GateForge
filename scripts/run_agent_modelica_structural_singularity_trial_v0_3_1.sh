#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${GATEFORGE_AGENT_STRUCTURAL_SINGULARITY_TRIAL_OUT_DIR:-artifacts/agent_modelica_structural_singularity_trial_v0_3_1}"

python3 -m gateforge.agent_modelica_structural_singularity_trial_v0_3_1 \
  --out-dir "$OUT_DIR"
