#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/mutation_dashboard_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.log

MUTATION_BACKEND=mock MUTATION_COUNT=8 bash scripts/demo_mutation_pack_v0.sh >/dev/null
MUTATION_BACKEND=mock MUTATION_COUNT=24 bash scripts/demo_mutation_pack_v1.sh >/dev/null
bash scripts/demo_mutation_pack_compare.sh >/dev/null

python3 -m gateforge.mutation_history \
  --record artifacts/mutation_pack_v0/metrics.json \
  --record artifacts/mutation_pack_v1/metrics.json \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/history_summary.json" \
  --report-out "$OUT_DIR/history_summary.md" >/dev/null

cat > "$OUT_DIR/history_previous.json" <<'JSON'
{
  "total_records": 1,
  "latest_match_rate": 0.9,
  "latest_gate_pass_rate": 0.9
}
JSON

python3 -m gateforge.mutation_history_trend \
  --current "$OUT_DIR/history_summary.json" \
  --previous "$OUT_DIR/history_previous.json" \
  --out "$OUT_DIR/history_trend.json" \
  --report-out "$OUT_DIR/history_trend.md" >/dev/null

python3 -m gateforge.mutation_dashboard \
  --metrics artifacts/mutation_pack_v1/metrics.json \
  --history "$OUT_DIR/history_summary.json" \
  --trend "$OUT_DIR/history_trend.json" \
  --compare artifacts/mutation_pack_compare_demo/summary.json \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
