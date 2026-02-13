#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/review_kpi_demo

bash scripts/demo_review_ledger.sh

cp artifacts/review_ledger_demo/ledger.jsonl artifacts/review_kpi_demo/ledger.jsonl

python3 -m gateforge.review_ledger \
  --ledger artifacts/review_kpi_demo/ledger.jsonl \
  --summary-out artifacts/review_kpi_demo/kpi_summary.json \
  --report-out artifacts/review_kpi_demo/kpi_summary.md

cat artifacts/review_kpi_demo/kpi_summary.json
cat artifacts/review_kpi_demo/kpi_summary.md

python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("artifacts/review_kpi_demo/kpi_summary.json").read_text(encoding="utf-8"))
kpis = payload.get("kpis", {})
if payload.get("total_records", 0) < 2:
    raise SystemExit(1)
if "approval_rate" not in kpis or "fail_rate" not in kpis:
    raise SystemExit(1)
if not isinstance(kpis.get("review_volume_last_7_days", []), list):
    raise SystemExit(1)
PY
