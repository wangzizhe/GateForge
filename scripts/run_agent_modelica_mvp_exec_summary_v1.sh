#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_MVP_EXEC_SUMMARY_OUT_DIR:-artifacts/agent_modelica_mvp_exec_summary_v1}"
THREE_ROUND_SUMMARY="${GATEFORGE_AGENT_THREE_ROUND_SUMMARY:-artifacts/agent_modelica_mvp_before_after_v1_rounds/summary.json}"
TOP2_SUMMARY="${GATEFORGE_AGENT_TOP2_SUMMARY:-artifacts/agent_modelica_top2_regression_challenge_v1/top2_summary.json}"
RETRIEVAL_AB_SUMMARY="${GATEFORGE_AGENT_RETRIEVAL_AB_SUMMARY:-artifacts/agent_modelica_retrieval_ab_v1/ab_summary.json}"
CHALLENGE_COMPARE="${GATEFORGE_AGENT_CHALLENGE_COMPARE:-artifacts/agent_modelica_top2_regression_challenge_v1/compare.json}"

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_mvp_exec_summary_v1 \
  --three-round-summary "$THREE_ROUND_SUMMARY" \
  --top2-summary "$TOP2_SUMMARY" \
  --retrieval-ab-summary "$RETRIEVAL_AB_SUMMARY" \
  --challenge-compare "$CHALLENGE_COMPARE" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

cat "$OUT_DIR/summary.json"
