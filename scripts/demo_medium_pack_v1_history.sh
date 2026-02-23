#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/benchmark_medium_v1"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/history.jsonl "$OUT_DIR"/history_summary.json "$OUT_DIR"/history_summary.md "$OUT_DIR"/summary_degraded.json

if [[ ! -f "$OUT_DIR/summary.json" ]]; then
  bash scripts/demo_medium_pack_v1.sh >/dev/null
fi

python3 - <<'PY'
import json
from pathlib import Path

src = Path("artifacts/benchmark_medium_v1/summary.json")
dst = Path("artifacts/benchmark_medium_v1/summary_degraded.json")
payload = json.loads(src.read_text(encoding="utf-8"))
payload["pass_count"] = 9
payload["fail_count"] = 3
payload["pass_rate"] = 0.75
payload["mismatch_case_count"] = 3
dst.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

python3 -m gateforge.medium_benchmark_history \
  --record "$OUT_DIR/summary.json" \
  --record "$OUT_DIR/summary_degraded.json" \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/history_summary.json" \
  --report-out "$OUT_DIR/history_summary.md" \
  --min-pass-rate 0.9 \
  --mismatch-threshold 1

cat "$OUT_DIR/history_summary.json"
cat "$OUT_DIR/history_summary.md"
