#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_history_demo

cat > artifacts/governance_history_demo/snapshot_1.json <<'JSON'
{
  "status": "PASS",
  "kpis": {
    "strict_downgrade_rate": 0.0,
    "review_recovery_rate": 0.8,
    "strict_non_pass_rate": 0.1,
    "approval_rate": 0.8,
    "fail_rate": 0.2
  },
  "risks": []
}
JSON

cat > artifacts/governance_history_demo/snapshot_2.json <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "kpis": {
    "strict_downgrade_rate": 0.3,
    "review_recovery_rate": 0.5,
    "strict_non_pass_rate": 0.4,
    "approval_rate": 0.6,
    "fail_rate": 0.4
  },
  "risks": [
    "strict_profile_downgrade_detected"
  ]
}
JSON

cat > artifacts/governance_history_demo/snapshot_3.json <<'JSON'
{
  "status": "FAIL",
  "kpis": {
    "strict_downgrade_rate": 0.5,
    "review_recovery_rate": 0.3,
    "strict_non_pass_rate": 0.8,
    "approval_rate": 0.4,
    "fail_rate": 0.6
  },
  "risks": [
    "ci_matrix_failed",
    "strict_non_pass_rate_high"
  ]
}
JSON

HISTORY_DIR="artifacts/governance_history_demo/history"
rm -rf "$HISTORY_DIR"

python3 -m gateforge.governance_history \
  --history-dir "$HISTORY_DIR" \
  --snapshot artifacts/governance_history_demo/snapshot_1.json \
  --label s1 \
  --last-n 3 \
  --out artifacts/governance_history_demo/summary_after_s1.json

python3 -m gateforge.governance_history \
  --history-dir "$HISTORY_DIR" \
  --snapshot artifacts/governance_history_demo/snapshot_2.json \
  --label s2 \
  --last-n 3 \
  --out artifacts/governance_history_demo/summary_after_s2.json

python3 -m gateforge.governance_history \
  --history-dir "$HISTORY_DIR" \
  --snapshot artifacts/governance_history_demo/snapshot_3.json \
  --label s3 \
  --last-n 3 \
  --out artifacts/governance_history_demo/summary.json \
  --report artifacts/governance_history_demo/summary.md

cat artifacts/governance_history_demo/summary.json
cat artifacts/governance_history_demo/summary.md

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/governance_history_demo/summary.json").read_text(encoding="utf-8"))
if payload.get("total_records") != 3:
    raise SystemExit(1)
if payload.get("window_size") != 3:
    raise SystemExit(1)
if payload.get("latest_status") != "FAIL":
    raise SystemExit(1)
transitions = payload.get("transitions", [])
if len(transitions) != 2:
    raise SystemExit(1)
if payload.get("transition_kpis", {}).get("worse_count", 0) < 1:
    raise SystemExit(1)
PY
