#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

bash scripts/demo_medium_pack_v1.sh >/dev/null

python3 -m gateforge.medium_benchmark_analyze \
  --summary artifacts/benchmark_medium_v1/summary.json \
  --out artifacts/benchmark_medium_v1/analysis.json \
  --report-out artifacts/benchmark_medium_v1/analysis.md

cat artifacts/benchmark_medium_v1/analysis.json
cat artifacts/benchmark_medium_v1/analysis.md
