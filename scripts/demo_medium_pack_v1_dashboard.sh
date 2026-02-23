#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/benchmark_medium_v1"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/dashboard.json "$OUT_DIR"/dashboard.md "$OUT_DIR"/history_trend.json "$OUT_DIR"/history_trend.md "$OUT_DIR"/advisor.json "$OUT_DIR"/advisor.md

bash scripts/demo_medium_pack_v1_analysis.sh >/dev/null
bash scripts/demo_medium_pack_v1_history.sh >/dev/null

cat > "$OUT_DIR/history_summary_previous.json" <<'JSON'
{
  "total_records": 1,
  "latest_pack_id": "medium_pack_v1",
  "latest_pass_rate": 1.0,
  "avg_pass_rate": 1.0,
  "mismatch_case_total": 0,
  "alerts": []
}
JSON

python3 -m gateforge.medium_benchmark_history_trend \
  --summary "$OUT_DIR/history_summary.json" \
  --previous-summary "$OUT_DIR/history_summary_previous.json" \
  --out "$OUT_DIR/history_trend.json" \
  --report-out "$OUT_DIR/history_trend.md"

python3 -m gateforge.medium_benchmark_advisor \
  --history-summary "$OUT_DIR/history_summary.json" \
  --trend-summary "$OUT_DIR/history_trend.json" \
  --out "$OUT_DIR/advisor.json" \
  --report-out "$OUT_DIR/advisor.md"

python3 -m gateforge.medium_benchmark_dashboard \
  --summary "$OUT_DIR/summary.json" \
  --analysis "$OUT_DIR/analysis.json" \
  --history "$OUT_DIR/history_summary.json" \
  --trend "$OUT_DIR/history_trend.json" \
  --advisor "$OUT_DIR/advisor.json" \
  --out "$OUT_DIR/dashboard.json" \
  --report-out "$OUT_DIR/dashboard.md"

cat "$OUT_DIR/dashboard.json"
cat "$OUT_DIR/dashboard.md"
