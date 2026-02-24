#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/mutation_pack_compare_demo
rm -f artifacts/mutation_pack_compare_demo/*.json artifacts/mutation_pack_compare_demo/*.md

MUTATION_BACKEND=mock MUTATION_COUNT=8 bash scripts/demo_mutation_pack_v0.sh >/dev/null
MUTATION_BACKEND=mock MUTATION_COUNT=24 bash scripts/demo_mutation_pack_v1.sh >/dev/null

python3 -m gateforge.mutation_pack_compare \
  --baseline artifacts/mutation_pack_v0/metrics.json \
  --candidate artifacts/mutation_pack_v1/metrics.json \
  --out artifacts/mutation_pack_compare_demo/summary.json \
  --report-out artifacts/mutation_pack_compare_demo/summary.md

cat artifacts/mutation_pack_compare_demo/summary.json
cat artifacts/mutation_pack_compare_demo/summary.md
