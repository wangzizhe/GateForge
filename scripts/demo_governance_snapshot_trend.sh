#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_snapshot_trend_demo

# Build a previous snapshot baseline (manually controlled to show trend signal).
cat > artifacts/governance_snapshot_trend_demo/previous_summary.json <<'JSON'
{
  "status": "PASS",
  "kpis": {
    "strict_downgrade_rate": 0.0,
    "review_recovery_rate": 0.8,
    "strict_non_pass_rate": 0.1,
    "approval_rate": 0.7,
    "fail_rate": 0.2
  },
  "risks": [
    "review_recovery_rate_low"
  ]
}
JSON

bash scripts/demo_governance_snapshot.sh
# Re-pin ci_matrix summary to a non-recursive selection before trend compare.
RUN_GOVERNANCE_SNAPSHOT_DEMO=0 RUN_GOVERNANCE_SNAPSHOT_TREND_DEMO=0 RUN_GOVERNANCE_PROMOTE_DEMO=0 bash scripts/demo_ci_matrix.sh

python3 -m gateforge.governance_report \
  --repair-batch-summary artifacts/repair_batch_compare_demo/summary.json \
  --review-ledger-summary artifacts/review_kpi_demo/kpi_summary.json \
  --ci-matrix-summary artifacts/ci_matrix_summary.json \
  --previous-summary artifacts/governance_snapshot_trend_demo/previous_summary.json \
  --out artifacts/governance_snapshot_trend_demo/summary.json \
  --report artifacts/governance_snapshot_trend_demo/summary.md

cat artifacts/governance_snapshot_trend_demo/summary.json
cat artifacts/governance_snapshot_trend_demo/summary.md

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/governance_snapshot_trend_demo/summary.json").read_text(encoding="utf-8"))
trend = payload.get("trend", {})
if not trend:
    raise SystemExit(1)
if "status_transition" not in trend:
    raise SystemExit(1)
if "kpi_delta" not in trend:
    raise SystemExit(1)
if not isinstance(trend.get("new_risks", []), list):
    raise SystemExit(1)
if not isinstance(trend.get("resolved_risks", []), list):
    raise SystemExit(1)
PY
