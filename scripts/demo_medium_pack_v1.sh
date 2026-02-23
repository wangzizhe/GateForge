#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/benchmark_medium_v1"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/summary.json "$OUT_DIR"/summary.md

set +e
python3 -m gateforge.medium_benchmark \
  --pack benchmarks/medium_pack_v1.json \
  --out-dir "$OUT_DIR" \
  --summary-out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"
BENCH_RC=$?
set -e
if [[ "$BENCH_RC" -ne 0 ]]; then
  echo "medium_pack_v1 returned non-zero (continuing with generated artifacts): rc=$BENCH_RC"
fi

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
