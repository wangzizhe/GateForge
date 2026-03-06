#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_RETRIEVAL_AB_OUT_DIR:-artifacts/agent_modelica_retrieval_ab_v1}"
DEFAULT_PROFILE_PATH="benchmarks/agent_modelica_mvp_repair_v1.json"
if [ -f "benchmarks/private/agent_modelica_mvp_repair_v1.json" ]; then
  DEFAULT_PROFILE_PATH="benchmarks/private/agent_modelica_mvp_repair_v1.json"
fi
PROFILE_PATH="${GATEFORGE_AGENT_MVP_PROFILE_PATH:-$DEFAULT_PROFILE_PATH}"
RUN_TAG="${GATEFORGE_AGENT_RETRIEVAL_AB_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
OFF_MEM="${GATEFORGE_AGENT_RETRIEVAL_AB_OFF_MEMORY:-data/private_failure_corpus/agent_modelica_repair_memory_ab_off_v1.json}"

OFF_DIR="$OUT_DIR/off"
ON_DIR="$OUT_DIR/on"
SUMMARY_PATH="$OUT_DIR/ab_summary.json"
REPORT_PATH="$OUT_DIR/ab_summary.md"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
rm -f "$OFF_MEM"

set +e
GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR="$OFF_DIR" \
GATEFORGE_AGENT_WEEK_TAG="ab_off_${RUN_TAG}" \
GATEFORGE_AGENT_ALLOW_BASELINE_FAIL="1" \
GATEFORGE_AGENT_REPAIR_HISTORY_PATH="$OFF_MEM" \
bash scripts/run_agent_modelica_weekly_chain_v1.sh >/tmp/gf_ab_off.log 2>&1
OFF_RC=$?

GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR="$ON_DIR" \
GATEFORGE_AGENT_WEEK_TAG="ab_on_${RUN_TAG}" \
GATEFORGE_AGENT_ALLOW_BASELINE_FAIL="1" \
bash scripts/run_agent_modelica_weekly_chain_v1.sh >/tmp/gf_ab_on.log 2>&1
ON_RC=$?
set -e

if [ ! -f "$OFF_DIR/summary.json" ]; then
  echo "missing off summary: $OFF_DIR/summary.json (rc=$OFF_RC)" >&2
  exit 1
fi
if [ ! -f "$ON_DIR/summary.json" ]; then
  echo "missing on summary: $ON_DIR/summary.json (rc=$ON_RC)" >&2
  exit 1
fi

python3 - "$OFF_DIR" "$ON_DIR" "$SUMMARY_PATH" "$REPORT_PATH" "$OFF_RC" "$ON_RC" <<'PY'
from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _run_metrics(run_dir: Path) -> dict:
    summary = _load(run_dir / "summary.json")
    results = _load(run_dir / "baseline" / "run_results.json")
    records = results.get("records") if isinstance(results.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]
    retrieved = []
    for row in records:
        audit = row.get("repair_audit") if isinstance(row.get("repair_audit"), dict) else {}
        value = audit.get("retrieved_example_count")
        if isinstance(value, (int, float)):
            retrieved.append(float(value))
    return {
        "status": summary.get("status"),
        "success_at_k_pct": summary.get("success_at_k_pct"),
        "regression_count": summary.get("regression_count"),
        "physics_fail_count": summary.get("physics_fail_count"),
        "median_time_to_pass_sec": summary.get("median_time_to_pass_sec"),
        "median_repair_rounds": summary.get("median_repair_rounds"),
        "task_count": len(records),
        "mean_retrieved_example_count": round(statistics.mean(retrieved), 3) if retrieved else 0.0,
        "nonzero_retrieval_tasks": len([x for x in retrieved if x > 0.0]),
        "path": str(run_dir),
    }


def _num(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


off = _run_metrics(Path(sys.argv[1]))
on = _run_metrics(Path(sys.argv[2]))
out = Path(sys.argv[3])
report = Path(sys.argv[4])
off_rc = int(sys.argv[5])
on_rc = int(sys.argv[6])

payload = {
    "schema_version": "agent_modelica_retrieval_ab_checkpoint_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS" if off_rc == 0 and on_rc == 0 else "NEEDS_REVIEW",
    "execution_rc": {"off": off_rc, "on": on_rc},
    "off": off,
    "on": on,
    "delta_on_minus_off": {
        "success_at_k_pct": round(_num(on.get("success_at_k_pct")) - _num(off.get("success_at_k_pct")), 2),
        "regression_count": round(_num(on.get("regression_count")) - _num(off.get("regression_count")), 2),
        "physics_fail_count": round(_num(on.get("physics_fail_count")) - _num(off.get("physics_fail_count")), 2),
        "median_time_to_pass_sec": round(_num(on.get("median_time_to_pass_sec")) - _num(off.get("median_time_to_pass_sec")), 2),
        "mean_retrieved_example_count": round(
            _num(on.get("mean_retrieved_example_count")) - _num(off.get("mean_retrieved_example_count")), 3
        ),
        "nonzero_retrieval_tasks": int(_num(on.get("nonzero_retrieval_tasks")) - _num(off.get("nonzero_retrieval_tasks"))),
    },
}

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
lines = [
    "# GateForge Agent Modelica Retrieval A/B Checkpoint v1",
    "",
    f"- status: `{payload.get('status')}`",
    f"- off_status: `{off.get('status')}`",
    f"- on_status: `{on.get('status')}`",
    f"- delta_success_at_k_pct: `{payload['delta_on_minus_off'].get('success_at_k_pct')}`",
    f"- delta_regression_count: `{payload['delta_on_minus_off'].get('regression_count')}`",
    f"- delta_median_time_to_pass_sec: `{payload['delta_on_minus_off'].get('median_time_to_pass_sec')}`",
    f"- delta_mean_retrieved_example_count: `{payload['delta_on_minus_off'].get('mean_retrieved_example_count')}`",
    "",
]
report.write_text("\n".join(lines), encoding="utf-8")
print(json.dumps(payload))
PY

cat "$SUMMARY_PATH"
