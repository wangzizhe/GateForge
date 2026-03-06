#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROFILE_PATH="${GATEFORGE_AGENT_MVP_PROFILE_PATH:-benchmarks/agent_modelica_mvp_repair_v1.json}"
OUT_DIR="${GATEFORGE_AGENT_MVP_ROLLING_FOCUS_AB_OUT_DIR:-artifacts/agent_modelica_mvp_rolling_focus_ab_v1}"
RUNS_PER_ARM="${GATEFORGE_AGENT_MVP_ROLLING_FOCUS_AB_RUNS_PER_ARM:-2}"
RUN_TAG_BASE="${GATEFORGE_AGENT_MVP_ROLLING_FOCUS_AB_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
AB_INTERVAL="${GATEFORGE_AGENT_RETRIEVAL_AB_INTERVAL:-0}"
HOLDOUT_INTERVAL="${GATEFORGE_AGENT_HOLDOUT_CHECKPOINT_INTERVAL:-0}"

mkdir -p "$OUT_DIR"
rm -rf "$OUT_DIR/on" "$OUT_DIR/off"

run_arm() {
  local arm="$1"
  local rolling_enable="$2"
  local arm_dir="$OUT_DIR/$arm"
  mkdir -p "$arm_dir"
  local i
  for ((i=1; i<=RUNS_PER_ARM; i++)); do
    local tag="${RUN_TAG_BASE}_${arm}_r${i}"
    GATEFORGE_AGENT_MVP_DAILY_LOOP_OUT_DIR="$arm_dir" \
    GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
    GATEFORGE_AGENT_MVP_DAILY_TAG="$tag" \
    GATEFORGE_AGENT_MVP_DAILY_ROLLING_FOCUS_ENABLE="$rolling_enable" \
    GATEFORGE_AGENT_RETRIEVAL_AB_INTERVAL="$AB_INTERVAL" \
    GATEFORGE_AGENT_HOLDOUT_CHECKPOINT_INTERVAL="$HOLDOUT_INTERVAL" \
    bash scripts/run_agent_modelica_mvp_daily_loop_v1.sh >/tmp/gf_mvp_roll_${arm}_${i}.log 2>&1
  done
}

run_arm "on" "1"
run_arm "off" "0"

python3 - "$OUT_DIR/on/summary.json" "$OUT_DIR/off/summary.json" "$OUT_DIR/compare.json" "$OUT_DIR/compare.md" "$RUNS_PER_ARM" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _num(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


on = _load(sys.argv[1])
off = _load(sys.argv[2])
out_json = Path(sys.argv[3])
out_md = Path(sys.argv[4])
runs_per_arm = int(sys.argv[5])

on_success = _num((on.get("daily") or {}).get("success_at_k_pct"))
off_success = _num((off.get("daily") or {}).get("success_at_k_pct"))
on_reg = _num((on.get("daily") or {}).get("regression_count"))
off_reg = _num((off.get("daily") or {}).get("regression_count"))
on_focus_hit = _num(on.get("focus_hit_rate_pct"))
off_focus_hit = _num(off.get("focus_hit_rate_pct"))

payload = {
    "schema_version": "agent_modelica_mvp_rolling_focus_ab_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS",
    "runs_per_arm": runs_per_arm,
    "on": {
        "summary_path": sys.argv[1],
        "status": on.get("status"),
        "success_at_k_pct": on_success,
        "regression_count": on_reg,
        "focus_hit_rate_pct": on_focus_hit,
    },
    "off": {
        "summary_path": sys.argv[2],
        "status": off.get("status"),
        "success_at_k_pct": off_success,
        "regression_count": off_reg,
        "focus_hit_rate_pct": off_focus_hit,
    },
    "delta_on_minus_off": {
        "success_at_k_pct": round(on_success - off_success, 2) if on_success is not None and off_success is not None else None,
        "regression_count": round(on_reg - off_reg, 2) if on_reg is not None and off_reg is not None else None,
        "focus_hit_rate_pct": round(on_focus_hit - off_focus_hit, 2) if on_focus_hit is not None and off_focus_hit is not None else None,
    },
}
out_json.parent.mkdir(parents=True, exist_ok=True)
out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
lines = [
    "# GateForge Agent Modelica MVP Rolling Focus A/B v1",
    "",
    f"- runs_per_arm: `{payload.get('runs_per_arm')}`",
    f"- on_success_at_k_pct: `{(payload.get('on') or {}).get('success_at_k_pct')}`",
    f"- off_success_at_k_pct: `{(payload.get('off') or {}).get('success_at_k_pct')}`",
    f"- delta_success_at_k_pct: `{(payload.get('delta_on_minus_off') or {}).get('success_at_k_pct')}`",
    f"- on_regression_count: `{(payload.get('on') or {}).get('regression_count')}`",
    f"- off_regression_count: `{(payload.get('off') or {}).get('regression_count')}`",
    f"- delta_regression_count: `{(payload.get('delta_on_minus_off') or {}).get('regression_count')}`",
    f"- on_focus_hit_rate_pct: `{(payload.get('on') or {}).get('focus_hit_rate_pct')}`",
    f"- off_focus_hit_rate_pct: `{(payload.get('off') or {}).get('focus_hit_rate_pct')}`",
    f"- delta_focus_hit_rate_pct: `{(payload.get('delta_on_minus_off') or {}).get('focus_hit_rate_pct')}`",
    "",
]
out_md.write_text("\n".join(lines), encoding="utf-8")
print(json.dumps(payload))
PY

cat "$OUT_DIR/compare.json"
