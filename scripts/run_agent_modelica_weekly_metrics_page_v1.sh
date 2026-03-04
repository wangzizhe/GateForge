#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_WEEKLY_METRICS_OUT_DIR:-artifacts/agent_modelica_weekly_metrics_v1}"
BASELINE_SUMMARY="${GATEFORGE_AGENT_WEEKLY_BASELINE_SUMMARY:-artifacts/agent_modelica_layered_baseline_v1/summary.json}"
WEEK_TAG="${GATEFORGE_AGENT_WEEK_TAG:-$(date -u +%G-W%V)}"

if [ ! -f "$BASELINE_SUMMARY" ]; then
  echo "Baseline summary not found: $BASELINE_SUMMARY" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_weekly_metrics_page_v1 \
  --baseline-summary "$BASELINE_SUMMARY" \
  --week-tag "$WEEK_TAG" \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/page.json" \
  --report-out "$OUT_DIR/page.md"

cat "$OUT_DIR/page.json"
