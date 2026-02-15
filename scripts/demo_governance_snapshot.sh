#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_snapshot_demo

bash scripts/demo_review_kpis.sh
bash scripts/demo_repair_batch_compare.sh
bash scripts/demo_invariant_repair_profile_compare.sh
bash scripts/demo_ci_matrix.sh --none --checker-demo

python3 -m gateforge.governance_report \
  --repair-batch-summary artifacts/repair_batch_compare_demo/summary.json \
  --review-ledger-summary artifacts/review_kpi_demo/kpi_summary.json \
  --ci-matrix-summary artifacts/ci_matrix_summary.json \
  --invariant-repair-compare-summary artifacts/invariant_repair_profile_compare_demo/compare.json \
  --out artifacts/governance_snapshot_demo/summary.json \
  --report artifacts/governance_snapshot_demo/summary.md

cat artifacts/governance_snapshot_demo/summary.json
cat artifacts/governance_snapshot_demo/summary.md

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/governance_snapshot_demo/summary.json").read_text(encoding="utf-8"))
status = payload.get("status")
if status not in {"PASS", "NEEDS_REVIEW", "FAIL"}:
    raise SystemExit(1)
if not isinstance(payload.get("risks", []), list):
    raise SystemExit(1)
if "kpis" not in payload:
    raise SystemExit(1)
PY
