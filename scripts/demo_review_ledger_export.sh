#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/review_export_demo
rm -f artifacts/review_export_demo/ledger.jsonl
rm -f artifacts/review_export_demo/fail_records.json artifacts/review_export_demo/proposal_records.json
rm -f artifacts/review_export_demo/fail_summary.json artifacts/review_export_demo/fail_summary.md
rm -f artifacts/review_export_demo/proposal_summary.json artifacts/review_export_demo/proposal_summary.md

bash scripts/demo_review_ledger.sh

LEDGER="artifacts/review_ledger_demo/ledger.jsonl"
FAIL_EXPORT="artifacts/review_export_demo/fail_records.json"
PROPOSAL_EXPORT="artifacts/review_export_demo/proposal_records.json"

python3 -m gateforge.review_ledger \
  --ledger "$LEDGER" \
  --final-status FAIL \
  --export-out "$FAIL_EXPORT" \
  --summary-out artifacts/review_export_demo/fail_summary.json \
  --report-out artifacts/review_export_demo/fail_summary.md

python3 -m gateforge.review_ledger \
  --ledger "$LEDGER" \
  --proposal-id review-demo-001 \
  --export-out "$PROPOSAL_EXPORT" \
  --summary-out artifacts/review_export_demo/proposal_summary.json \
  --report-out artifacts/review_export_demo/proposal_summary.md

cat "$FAIL_EXPORT"
cat "$PROPOSAL_EXPORT"

python3 - <<'PY'
import json
from pathlib import Path

fail_payload = json.loads(Path("artifacts/review_export_demo/fail_records.json").read_text(encoding="utf-8"))
proposal_payload = json.loads(Path("artifacts/review_export_demo/proposal_records.json").read_text(encoding="utf-8"))

if fail_payload.get("total_records", 0) < 1:
    raise SystemExit(1)
for row in fail_payload.get("records", []):
    if row.get("final_status") != "FAIL":
        raise SystemExit(1)

if proposal_payload.get("total_records", 0) < 1:
    raise SystemExit(1)
for row in proposal_payload.get("records", []):
    if row.get("proposal_id") != "review-demo-001":
        raise SystemExit(1)
PY
