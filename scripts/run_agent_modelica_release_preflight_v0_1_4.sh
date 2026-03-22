#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export GATEFORGE_AGENT_RELEASE_OUT_DIR="${GATEFORGE_AGENT_RELEASE_OUT_DIR:-artifacts/release_v0_1_4}"
V4_REPLAN_SUMMARY="${GATEFORGE_AGENT_RELEASE_V014_V4_REPLAN_SUMMARY:-artifacts/agent_modelica_source_blind_multistep_live_evidence_v1/runs/source_blind_multistep_live_budgetreplan_07/source_blind_multistep_baseline_summary.json}"
V5_BRANCH_SUMMARY="${GATEFORGE_AGENT_RELEASE_V014_V5_BRANCH_SUMMARY:-artifacts/agent_modelica_source_blind_multistep_live_evidence_v1/runs/source_blind_multistep_live_v5_01/source_blind_multistep_baseline_summary.json}"

BASE_RC=0
set +e
bash scripts/run_agent_modelica_release_preflight_v0_1_3.sh
BASE_RC=$?
set -e

EVIDENCE_RC=0
if [ "${GATEFORGE_AGENT_RELEASE_SKIP_VERSION_EVIDENCE:-0}" != "1" ]; then
  set +e
  python3 -m gateforge.agent_modelica_release_preflight_v0_1_4_evidence \
    --summary "$GATEFORGE_AGENT_RELEASE_OUT_DIR/release_preflight_summary.json" \
    --v4-replan-summary "$V4_REPLAN_SUMMARY" \
    --v5-branch-summary "$V5_BRANCH_SUMMARY"
  EVIDENCE_RC=$?
  set -e
fi

if [ "$BASE_RC" -ne 0 ] || [ "$EVIDENCE_RC" -ne 0 ]; then
  exit 1
fi
