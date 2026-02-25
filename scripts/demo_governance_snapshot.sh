#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_snapshot_demo

bash scripts/demo_review_kpis.sh
bash scripts/demo_repair_batch_compare.sh
bash scripts/demo_invariant_repair_profile_compare.sh
bash scripts/demo_mutation_dashboard.sh
bash scripts/demo_ci_matrix.sh --none --checker-demo
bash scripts/demo_dataset_history.sh >/dev/null
bash scripts/demo_dataset_governance_history.sh >/dev/null

python3 -m gateforge.governance_report \
  --repair-batch-summary artifacts/repair_batch_compare_demo/summary.json \
  --review-ledger-summary artifacts/review_kpi_demo/kpi_summary.json \
  --ci-matrix-summary artifacts/ci_matrix_summary.json \
  --invariant-repair-compare-summary artifacts/invariant_repair_profile_compare_demo/compare.json \
  --mutation-dashboard-summary artifacts/mutation_dashboard_demo/summary.json \
  --dataset-pipeline-summary artifacts/dataset_pipeline_demo/summary.json \
  --dataset-history-summary artifacts/dataset_history_demo/history_summary.json \
  --dataset-history-trend artifacts/dataset_history_demo/history_trend.json \
  --dataset-governance-summary artifacts/dataset_policy_lifecycle_demo/ledger_summary.json \
  --dataset-governance-trend artifacts/dataset_governance_history_demo/trend.json \
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
