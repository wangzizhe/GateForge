#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export GATEFORGE_AGENT_RELEASE_OUT_DIR="${GATEFORGE_AGENT_RELEASE_OUT_DIR:-artifacts/release_v0_1_5}"
V4_REPLAN_SUMMARY="${GATEFORGE_AGENT_RELEASE_V015_V4_REPLAN_SUMMARY:-artifacts/agent_modelica_source_blind_multistep_live_evidence_v1/runs/source_blind_multistep_live_budgetreplan_07/source_blind_multistep_baseline_summary.json}"
V5_GEMINI_SUMMARY="${GATEFORGE_AGENT_RELEASE_V015_V5_GEMINI_SUMMARY:-artifacts/agent_modelica_source_blind_multistep_live_evidence_v1/runs/source_blind_multistep_live_v5_03/source_blind_multistep_baseline_summary.json}"
V5_RULE_SUMMARY="${GATEFORGE_AGENT_RELEASE_V015_V5_RULE_SUMMARY:-artifacts/agent_modelica_source_blind_multistep_live_evidence_v1/runs/source_blind_multistep_live_v5_rule_01/source_blind_multistep_baseline_summary.json}"

BASE_RC=0
set +e
bash scripts/run_agent_modelica_release_preflight_v0_1_4.sh
BASE_RC=$?
set -e

EVIDENCE_RC=0
if [ "${GATEFORGE_AGENT_RELEASE_SKIP_VERSION_EVIDENCE:-0}" != "1" ]; then
  DQ_GATE_PATH="${GATEFORGE_AGENT_RELEASE_V015_DQ_GATE:-artifacts/agent_modelica_weekly_chain_v1/weekly/decision_quality_gate.json}"
  DQ_GATE_ARG=""
  if [ -f "$DQ_GATE_PATH" ]; then
    DQ_GATE_ARG="--decision-quality-gate $DQ_GATE_PATH"
  fi
  L5_TREND_PATH="${GATEFORGE_AGENT_RELEASE_V015_L5_TREND:-artifacts/agent_modelica_l5_eval_v1/l5_performance_trend.json}"
  L5_TREND_ARG=""
  if [ -f "$L5_TREND_PATH" ]; then
    L5_TREND_ARG="--l5-performance-trend $L5_TREND_PATH"
  fi
  set +e
  # shellcheck disable=SC2086
  python3 -m gateforge.agent_modelica_release_preflight_v0_1_5_evidence \
    --summary "$GATEFORGE_AGENT_RELEASE_OUT_DIR/release_preflight_summary.json" \
    --v4-replan-summary "$V4_REPLAN_SUMMARY" \
    --v5-gemini-summary "$V5_GEMINI_SUMMARY" \
    --v5-rule-summary "$V5_RULE_SUMMARY" \
    $DQ_GATE_ARG \
    $L5_TREND_ARG
  EVIDENCE_RC=$?
  set -e
fi

if [ "$BASE_RC" -ne 0 ] || [ "$EVIDENCE_RC" -ne 0 ]; then
  exit 1
fi
