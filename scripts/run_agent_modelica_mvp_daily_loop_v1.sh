#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_MVP_DAILY_LOOP_OUT_DIR:-artifacts/agent_modelica_mvp_daily_loop_v1}"
PROFILE_PATH="${GATEFORGE_AGENT_MVP_PROFILE_PATH:-benchmarks/agent_modelica_mvp_repair_v1.json}"
RUN_TAG="${GATEFORGE_AGENT_MVP_DAILY_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
AB_INTERVAL="${GATEFORGE_AGENT_RETRIEVAL_AB_INTERVAL:-5}"
RUN_DIR="$OUT_DIR/runs/$RUN_TAG"
LEDGER_PATH="$OUT_DIR/history.jsonl"
SUMMARY_PATH="$OUT_DIR/summary.json"
REPORT_PATH="$OUT_DIR/summary.md"

mkdir -p "$OUT_DIR/runs"

set +e
GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR="$RUN_DIR" \
GATEFORGE_AGENT_WEEK_TAG="daily_${RUN_TAG}" \
GATEFORGE_AGENT_ALLOW_BASELINE_FAIL="1" \
bash scripts/run_agent_modelica_weekly_chain_v1.sh >/tmp/gf_mvp_daily.log 2>&1
RUN_RC=$?
set -e

if [ ! -f "$RUN_DIR/summary.json" ]; then
  echo "missing daily summary: $RUN_DIR/summary.json (rc=$RUN_RC)" >&2
  exit 1
fi

python3 - "$RUN_DIR/summary.json" "$LEDGER_PATH" "$RUN_TAG" "$RUN_RC" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
ledger = Path(sys.argv[2])
run_tag = sys.argv[3]
run_rc = int(sys.argv[4])

row = {
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_tag": run_tag,
    "execution_rc": run_rc,
    "status": summary.get("status"),
    "success_at_k_pct": summary.get("success_at_k_pct"),
    "regression_count": summary.get("regression_count"),
    "physics_fail_count": summary.get("physics_fail_count"),
    "source_summary": sys.argv[1],
}
ledger.parent.mkdir(parents=True, exist_ok=True)
with ledger.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=True) + "\n")
PY

RUN_COUNT="$(wc -l < "$LEDGER_PATH" | tr -d '[:space:]')"
AB_RAN="0"
AB_SUMMARY_PATH=""
if [ "$AB_INTERVAL" -gt 0 ] && [ $((RUN_COUNT % AB_INTERVAL)) -eq 0 ]; then
  AB_RAN="1"
  AB_OUT_DIR="$OUT_DIR/ab_checkpoint/$RUN_TAG"
  GATEFORGE_AGENT_RETRIEVAL_AB_OUT_DIR="$AB_OUT_DIR" \
  GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
  GATEFORGE_AGENT_RETRIEVAL_AB_TAG="$RUN_TAG" \
  bash scripts/run_agent_modelica_retrieval_ab_checkpoint_v1.sh >/tmp/gf_mvp_daily_ab.log 2>&1
  AB_SUMMARY_PATH="$AB_OUT_DIR/ab_summary.json"
fi

python3 - "$RUN_DIR/summary.json" "$SUMMARY_PATH" "$REPORT_PATH" "$RUN_TAG" "$RUN_COUNT" "$AB_RAN" "$AB_SUMMARY_PATH" "$RUN_RC" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

daily = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(sys.argv[2])
report = Path(sys.argv[3])
run_tag = sys.argv[4]
run_count = int(sys.argv[5])
ab_ran = bool(int(sys.argv[6]))
ab_summary = sys.argv[7]
run_rc = int(sys.argv[8])

payload = {
    "schema_version": "agent_modelica_mvp_daily_loop_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS" if str(daily.get("status")) == "PASS" and run_rc == 0 else "NEEDS_REVIEW",
    "run_tag": run_tag,
    "run_count": run_count,
    "execution_rc": run_rc,
    "ab_checkpoint_ran": ab_ran,
    "ab_summary_path": ab_summary or None,
    "daily": {
        "status": daily.get("status"),
        "success_at_k_pct": daily.get("success_at_k_pct"),
        "regression_count": daily.get("regression_count"),
        "physics_fail_count": daily.get("physics_fail_count"),
        "median_time_to_pass_sec": daily.get("median_time_to_pass_sec"),
    },
    "source_summary": sys.argv[1],
}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
lines = [
    "# GateForge Agent Modelica MVP Daily Loop v1",
    "",
    f"- status: `{payload.get('status')}`",
    f"- run_tag: `{payload.get('run_tag')}`",
    f"- run_count: `{payload.get('run_count')}`",
    f"- execution_rc: `{payload.get('execution_rc')}`",
    f"- success_at_k_pct: `{(payload.get('daily') or {}).get('success_at_k_pct')}`",
    f"- regression_count: `{(payload.get('daily') or {}).get('regression_count')}`",
    f"- physics_fail_count: `{(payload.get('daily') or {}).get('physics_fail_count')}`",
    f"- ab_checkpoint_ran: `{payload.get('ab_checkpoint_ran')}`",
    "",
]
report.write_text("\n".join(lines), encoding="utf-8")
print(json.dumps(payload))
PY

cat "$SUMMARY_PATH"
