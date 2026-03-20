#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export GATEFORGE_AGENT_RELEASE_OUT_DIR="${GATEFORGE_AGENT_RELEASE_OUT_DIR:-artifacts/release_v0_1_3}"
ROBUSTNESS_BASELINE_SUMMARY="${GATEFORGE_AGENT_RELEASE_V013_ROBUSTNESS_BASELINE_SUMMARY:-artifacts/agent_modelica_behavioral_robustness_live_evidence_v1/runs/behavioral_robustness_live_blind_det_03/behavioral_robustness_baseline_summary.json}"
ROBUSTNESS_DETERMINISTIC_SUMMARY="${GATEFORGE_AGENT_RELEASE_V013_ROBUSTNESS_DETERMINISTIC_SUMMARY:-artifacts/agent_modelica_behavioral_robustness_live_evidence_v1/runs/behavioral_robustness_live_blind_det_03/deterministic_on_live/summary.json}"
MULTISTEP_BASELINE_SUMMARY="${GATEFORGE_AGENT_RELEASE_V013_MULTISTEP_BASELINE_SUMMARY:-artifacts/agent_modelica_source_blind_multistep_live_evidence_v1/runs/source_blind_multistep_live_authority_01/source_blind_multistep_baseline_summary.json}"

BASE_RC=0
set +e
bash scripts/run_agent_modelica_release_preflight_v0_1_1.sh
BASE_RC=$?
set -e

EVIDENCE_RC=0
set +e
python3 -m gateforge.agent_modelica_release_preflight_v0_1_3_evidence \
  --summary "$GATEFORGE_AGENT_RELEASE_OUT_DIR/release_preflight_summary.json" \
  --robustness-baseline-summary "$ROBUSTNESS_BASELINE_SUMMARY" \
  --robustness-deterministic-summary "$ROBUSTNESS_DETERMINISTIC_SUMMARY" \
  --multistep-baseline-summary "$MULTISTEP_BASELINE_SUMMARY"
EVIDENCE_RC=$?
set -e

if [ "$BASE_RC" -ne 0 ] || [ "$EVIDENCE_RC" -ne 0 ]; then
  exit 1
fi
