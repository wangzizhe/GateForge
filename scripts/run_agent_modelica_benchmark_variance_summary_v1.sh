#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SPEC_PATH="${GATEFORGE_AGENT_BENCHMARK_VARIANCE_SPEC:-data/agent_modelica_benchmark_variance_spec_template_v1.json}"
OUT_PATH="${GATEFORGE_AGENT_BENCHMARK_VARIANCE_OUT:-artifacts/benchmark_variance_summary_v1/summary.json}"

python3 -m gateforge.agent_modelica_benchmark_variance_summary_v1 \
  --spec "$SPEC_PATH" \
  --out "$OUT_PATH"

cat "$OUT_PATH"
