#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_LAYERED_BASELINE_OUT_DIR:-artifacts/agent_modelica_layered_baseline_v1}"
MUTATION_MANIFEST="${GATEFORGE_AGENT_LAYERED_BASELINE_MANIFEST:-}"
REPAIR_HISTORY="${GATEFORGE_AGENT_LAYERED_BASELINE_REPAIR_HISTORY:-}"
FOCUS_QUEUE="${GATEFORGE_AGENT_LAYERED_BASELINE_FOCUS_QUEUE:-}"
INJECT_HARD_FAIL_COUNT="${GATEFORGE_AGENT_LAYERED_BASELINE_INJECT_HARD_FAIL_COUNT:-0}"
INJECT_SLOW_PASS_COUNT="${GATEFORGE_AGENT_LAYERED_BASELINE_INJECT_SLOW_PASS_COUNT:-0}"

if [ -z "$MUTATION_MANIFEST" ]; then
  for candidate in \
    "artifacts/agent_modelica_taskset_lock_v1_demo/mutation_manifest.json" \
    "artifacts/dataset_mutation_portfolio_balance_v1_demo/mutation_manifest.json" \
    "artifacts/run_private_model_mutation_scale_batch_v1_demo/batch/mutation_manifest.json" \
    "artifacts/run_private_model_mutation_largefirst_sprint_v1_demo/batch/mutation_manifest.json"
  do
    if [ -f "$candidate" ]; then
      MUTATION_MANIFEST="$candidate"
      break
    fi
  done
fi

if [ -z "$MUTATION_MANIFEST" ]; then
  echo "No mutation manifest found. Set GATEFORGE_AGENT_LAYERED_BASELINE_MANIFEST." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

CMD=(
  python3 -m gateforge.agent_modelica_layered_baseline_v1
  --mutation-manifest "$MUTATION_MANIFEST"
  --max-per-scale-failure-type 1
  --out-dir "$OUT_DIR"
  --out "$OUT_DIR/summary.json"
  --report-out "$OUT_DIR/summary.md"
)

if [ -n "$REPAIR_HISTORY" ]; then
  CMD+=(--repair-history "$REPAIR_HISTORY")
fi

if [ -n "$FOCUS_QUEUE" ]; then
  CMD+=(--focus-queue "$FOCUS_QUEUE")
fi

if [ "${INJECT_HARD_FAIL_COUNT}" -gt 0 ]; then
  CMD+=(--inject-hard-fail-count "$INJECT_HARD_FAIL_COUNT")
fi

if [ "${INJECT_SLOW_PASS_COUNT}" -gt 0 ]; then
  CMD+=(--inject-slow-pass-count "$INJECT_SLOW_PASS_COUNT")
fi

"${CMD[@]}"

cat "$OUT_DIR/summary.json"
