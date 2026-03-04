#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROFILE_PATH="${GATEFORGE_AGENT_MVP_PROFILE_PATH:-benchmarks/agent_modelica_mvp_repair_v1.json}"
OUT_DIR="${GATEFORGE_AGENT_MVP_BEFORE_AFTER_OUT_DIR:-artifacts/agent_modelica_mvp_before_after_v1}"
RUN_TAG_BASE="${GATEFORGE_AGENT_MVP_BEFORE_AFTER_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"

BEFORE_DIR="$OUT_DIR/before"
AFTER_DIR="$OUT_DIR/after"
COMPARE_JSON="$OUT_DIR/compare.json"
COMPARE_MD="$OUT_DIR/compare.md"

mkdir -p "$OUT_DIR"

echo "[mvp_before_after] profile=$PROFILE_PATH"
echo "[mvp_before_after] running BEFORE"
GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR="$BEFORE_DIR" \
GATEFORGE_AGENT_WEEK_TAG="${RUN_TAG_BASE}-before" \
bash scripts/run_agent_modelica_weekly_chain_v1.sh

FOCUS_QUEUE_PATH="$BEFORE_DIR/weekly/focus_queue_from_failure.json"
if [ ! -f "$FOCUS_QUEUE_PATH" ]; then
  echo "missing focus queue from before run: $FOCUS_QUEUE_PATH" >&2
  exit 1
fi

echo "[mvp_before_after] running AFTER"
GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR="$AFTER_DIR" \
GATEFORGE_AGENT_WEEK_TAG="${RUN_TAG_BASE}-after" \
GATEFORGE_AGENT_FOCUS_TARGETS_PATH="$FOCUS_QUEUE_PATH" \
bash scripts/run_agent_modelica_weekly_chain_v1.sh

python3 - "$BEFORE_DIR/summary.json" "$AFTER_DIR/summary.json" "$COMPARE_JSON" "$COMPARE_MD" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


before = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
after = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
out_json = Path(sys.argv[3])
out_md = Path(sys.argv[4])

def _to_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None

before_success = _to_float(before.get("success_at_k_pct"))
after_success = _to_float(after.get("success_at_k_pct"))
before_reg = _to_float(before.get("regression_count"))
after_reg = _to_float(after.get("regression_count"))
before_phy = _to_float(before.get("physics_fail_count"))
after_phy = _to_float(after.get("physics_fail_count"))

compare = {
    "schema_version": "agent_modelica_mvp_before_after_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS",
    "before": {
        "path": str(Path(sys.argv[1])),
        "status": before.get("status"),
        "success_at_k_pct": before.get("success_at_k_pct"),
        "regression_count": before.get("regression_count"),
        "physics_fail_count": before.get("physics_fail_count"),
    },
    "after": {
        "path": str(Path(sys.argv[2])),
        "status": after.get("status"),
        "success_at_k_pct": after.get("success_at_k_pct"),
        "regression_count": after.get("regression_count"),
        "physics_fail_count": after.get("physics_fail_count"),
    },
    "delta": {
        "success_at_k_pct": (
            round(after_success - before_success, 2) if isinstance(before_success, float) and isinstance(after_success, float) else None
        ),
        "regression_count": (
            round(after_reg - before_reg, 2) if isinstance(before_reg, float) and isinstance(after_reg, float) else None
        ),
        "physics_fail_count": (
            round(after_phy - before_phy, 2) if isinstance(before_phy, float) and isinstance(after_phy, float) else None
        ),
    },
}

out_json.parent.mkdir(parents=True, exist_ok=True)
out_json.write_text(json.dumps(compare, indent=2), encoding="utf-8")

lines = [
    "# GateForge Agent Modelica MVP Before/After v1",
    "",
    f"- status: `{compare.get('status')}`",
    f"- before_success_at_k_pct: `{compare['before'].get('success_at_k_pct')}`",
    f"- after_success_at_k_pct: `{compare['after'].get('success_at_k_pct')}`",
    f"- delta_success_at_k_pct: `{compare['delta'].get('success_at_k_pct')}`",
    f"- before_regression_count: `{compare['before'].get('regression_count')}`",
    f"- after_regression_count: `{compare['after'].get('regression_count')}`",
    f"- delta_regression_count: `{compare['delta'].get('regression_count')}`",
    f"- before_physics_fail_count: `{compare['before'].get('physics_fail_count')}`",
    f"- after_physics_fail_count: `{compare['after'].get('physics_fail_count')}`",
    f"- delta_physics_fail_count: `{compare['delta'].get('physics_fail_count')}`",
    "",
]
out_md.write_text("\n".join(lines), encoding="utf-8")
print(json.dumps(compare))
PY

cat "$COMPARE_JSON"
