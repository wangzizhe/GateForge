#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/review_ledger_demo

bash scripts/demo_review_resolution.sh

LEDGER="artifacts/review_ledger_demo/ledger.jsonl"
SUMMARY_JSON="artifacts/review_ledger_demo/ledger_summary.json"
SUMMARY_MD="artifacts/review_ledger_demo/ledger_summary.md"

cp artifacts/review/ledger.jsonl "$LEDGER"

python3 -m gateforge.review_ledger \
  --ledger "$LEDGER" \
  --summary-out "$SUMMARY_JSON" \
  --report-out "$SUMMARY_MD"

cat "$SUMMARY_JSON"
cat "$SUMMARY_MD"

python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("artifacts/review_ledger_demo/ledger_summary.json").read_text(encoding="utf-8"))
status = payload.get("status_counts", {})
if payload.get("total_records", 0) < 2:
    raise SystemExit(1)
if status.get("PASS", 0) < 1 or status.get("FAIL", 0) < 1:
    raise SystemExit(1)
PY
