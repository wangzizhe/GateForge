#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROFILE_PATH="${GATEFORGE_AGENT_MVP_PROFILE_PATH:-benchmarks/agent_modelica_mvp_repair_v1.json}"
OUT_DIR="${GATEFORGE_AGENT_MVP_MUTANT_REPAIR_LOOP_OUT_DIR:-artifacts/agent_modelica_mvp_mutant_repair_learning_loop_v1}"
RUN_TAG_BASE="${GATEFORGE_AGENT_MVP_MUTANT_REPAIR_LOOP_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
REPAIR_HISTORY_PATH="${GATEFORGE_AGENT_REPAIR_HISTORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"
PATCH_TEMPLATE_ADAPTATIONS_PATH="${GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH:-data/private_failure_corpus/agent_modelica_patch_template_adaptations_v1.json}"
RETRIEVAL_POLICY_PATH="${GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH:-data/private_failure_corpus/agent_modelica_retrieval_policy_v1.json}"
ALLOW_WEEKLY_FAIL="${GATEFORGE_AGENT_ALLOW_BASELINE_FAIL:-1}"

BEFORE_DIR="$OUT_DIR/before_weekly"
AFTER_DIR="$OUT_DIR/after_weekly"
HOLDOUT_BEFORE_DIR="$OUT_DIR/before_holdout"
HOLDOUT_AFTER_DIR="$OUT_DIR/after_holdout"
RECIPE_LOCK="$OUT_DIR/mutant_recipe_lock.json"
SUMMARY_JSON="$OUT_DIR/summary.json"
SUMMARY_MD="$OUT_DIR/summary.md"

mkdir -p "$OUT_DIR"
cp "$PROFILE_PATH" "$RECIPE_LOCK"

echo "[mvp_loop] step1 recipe lock: $RECIPE_LOCK"
echo "[mvp_loop] step2 before weekly repair run"
set +e
GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR="$BEFORE_DIR" \
GATEFORGE_AGENT_WEEK_TAG="${RUN_TAG_BASE}-before" \
GATEFORGE_AGENT_ALLOW_BASELINE_FAIL="$ALLOW_WEEKLY_FAIL" \
GATEFORGE_AGENT_REPAIR_HISTORY_PATH="$REPAIR_HISTORY_PATH" \
GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH="$PATCH_TEMPLATE_ADAPTATIONS_PATH" \
GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH="$RETRIEVAL_POLICY_PATH" \
bash scripts/run_agent_modelica_weekly_chain_v1.sh
BEFORE_WEEKLY_RC=$?
set -e

if [ ! -f "$BEFORE_DIR/summary.json" ]; then
  echo "missing before weekly summary: $BEFORE_DIR/summary.json (rc=$BEFORE_WEEKLY_RC)" >&2
  exit 1
fi
if [ ! -f "$BEFORE_DIR/baseline/taskset.json" ]; then
  echo "missing before taskset: $BEFORE_DIR/baseline/taskset.json" >&2
  exit 1
fi

echo "[mvp_loop] step3 before holdout (non-overlap)"
set +e
GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
GATEFORGE_AGENT_HOLDOUT_CHECKPOINT_OUT_DIR="$HOLDOUT_BEFORE_DIR" \
GATEFORGE_AGENT_HOLDOUT_EXCLUDE_TASKSET="$BEFORE_DIR/baseline/taskset.json" \
GATEFORGE_AGENT_REPAIR_HISTORY_PATH="$REPAIR_HISTORY_PATH" \
GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH="$PATCH_TEMPLATE_ADAPTATIONS_PATH" \
GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH="$RETRIEVAL_POLICY_PATH" \
bash scripts/run_agent_modelica_holdout_checkpoint_v1.sh
BEFORE_HOLDOUT_RC=$?
set -e

if [ ! -f "$HOLDOUT_BEFORE_DIR/summary.json" ]; then
  echo "missing before holdout summary: $HOLDOUT_BEFORE_DIR/summary.json (rc=$BEFORE_HOLDOUT_RC)" >&2
  exit 1
fi

FOCUS_TARGETS_PATH=""
if [ -f "$BEFORE_DIR/weekly/top_focus_templates.json" ]; then
  FOCUS_TARGETS_PATH="$BEFORE_DIR/weekly/top_focus_templates.json"
elif [ -f "$BEFORE_DIR/weekly/focus_queue_from_failure.json" ]; then
  FOCUS_TARGETS_PATH="$BEFORE_DIR/weekly/focus_queue_from_failure.json"
fi
if [ -z "$FOCUS_TARGETS_PATH" ]; then
  echo "missing focus targets from before run" >&2
  exit 1
fi

echo "[mvp_loop] step4 after weekly repair run (with focused targets)"
set +e
GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR="$AFTER_DIR" \
GATEFORGE_AGENT_WEEK_TAG="${RUN_TAG_BASE}-after" \
GATEFORGE_AGENT_FOCUS_TARGETS_PATH="$FOCUS_TARGETS_PATH" \
GATEFORGE_AGENT_ALLOW_BASELINE_FAIL="$ALLOW_WEEKLY_FAIL" \
GATEFORGE_AGENT_REPAIR_HISTORY_PATH="$REPAIR_HISTORY_PATH" \
GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH="$PATCH_TEMPLATE_ADAPTATIONS_PATH" \
GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH="$RETRIEVAL_POLICY_PATH" \
bash scripts/run_agent_modelica_weekly_chain_v1.sh
AFTER_WEEKLY_RC=$?
set -e

if [ ! -f "$AFTER_DIR/summary.json" ]; then
  echo "missing after weekly summary: $AFTER_DIR/summary.json (rc=$AFTER_WEEKLY_RC)" >&2
  exit 1
fi
if [ ! -f "$AFTER_DIR/baseline/taskset.json" ]; then
  echo "missing after taskset: $AFTER_DIR/baseline/taskset.json" >&2
  exit 1
fi

echo "[mvp_loop] step5 after holdout (non-overlap) + before/after compare"
set +e
GATEFORGE_AGENT_MVP_PROFILE_PATH="$PROFILE_PATH" \
GATEFORGE_AGENT_HOLDOUT_CHECKPOINT_OUT_DIR="$HOLDOUT_AFTER_DIR" \
GATEFORGE_AGENT_HOLDOUT_EXCLUDE_TASKSET="$AFTER_DIR/baseline/taskset.json" \
GATEFORGE_AGENT_REPAIR_HISTORY_PATH="$REPAIR_HISTORY_PATH" \
GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH="$PATCH_TEMPLATE_ADAPTATIONS_PATH" \
GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH="$RETRIEVAL_POLICY_PATH" \
bash scripts/run_agent_modelica_holdout_checkpoint_v1.sh
AFTER_HOLDOUT_RC=$?
set -e

if [ ! -f "$HOLDOUT_AFTER_DIR/summary.json" ]; then
  echo "missing after holdout summary: $HOLDOUT_AFTER_DIR/summary.json (rc=$AFTER_HOLDOUT_RC)" >&2
  exit 1
fi

python3 - "$BEFORE_DIR/summary.json" "$AFTER_DIR/summary.json" "$HOLDOUT_BEFORE_DIR/summary.json" "$HOLDOUT_AFTER_DIR/summary.json" "$SUMMARY_JSON" "$SUMMARY_MD" "$BEFORE_WEEKLY_RC" "$AFTER_WEEKLY_RC" "$BEFORE_HOLDOUT_RC" "$AFTER_HOLDOUT_RC" "$RECIPE_LOCK" "$FOCUS_TARGETS_PATH" "$REPAIR_HISTORY_PATH" "$PATCH_TEMPLATE_ADAPTATIONS_PATH" "$RETRIEVAL_POLICY_PATH" <<'PY'
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


before = _load(sys.argv[1])
after = _load(sys.argv[2])
before_holdout = _load(sys.argv[3])
after_holdout = _load(sys.argv[4])
out_json = Path(sys.argv[5])
out_md = Path(sys.argv[6])
before_weekly_rc = int(sys.argv[7])
after_weekly_rc = int(sys.argv[8])
before_holdout_rc = int(sys.argv[9])
after_holdout_rc = int(sys.argv[10])
recipe_lock = sys.argv[11]
focus_targets = sys.argv[12]
repair_history_path = sys.argv[13]
patch_adapt_path = sys.argv[14]
retrieval_policy_path = sys.argv[15]

before_success = _num(before.get("success_at_k_pct"))
after_success = _num(after.get("success_at_k_pct"))
before_reg = _num(before.get("regression_count"))
after_reg = _num(after.get("regression_count"))
before_holdout_success = _num(before_holdout.get("success_at_k_pct"))
after_holdout_success = _num(after_holdout.get("success_at_k_pct"))
before_holdout_reg = _num(before_holdout.get("regression_count"))
after_holdout_reg = _num(after_holdout.get("regression_count"))

payload = {
    "schema_version": "agent_modelica_mvp_mutant_repair_learning_loop_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS",
    "execution_rc": {
        "before_weekly": before_weekly_rc,
        "after_weekly": after_weekly_rc,
        "before_holdout": before_holdout_rc,
        "after_holdout": after_holdout_rc,
    },
    "recipe_lock_path": recipe_lock,
    "focus_targets_path": focus_targets,
    "private_assets": {
        "repair_history_path": repair_history_path,
        "patch_template_adaptations_path": patch_adapt_path,
        "retrieval_policy_path": retrieval_policy_path,
    },
    "before": {
        "weekly_status": before.get("status"),
        "weekly_success_at_k_pct": before.get("success_at_k_pct"),
        "weekly_regression_count": before.get("regression_count"),
        "holdout_status": before_holdout.get("status"),
        "holdout_success_at_k_pct": before_holdout.get("success_at_k_pct"),
        "holdout_regression_count": before_holdout.get("regression_count"),
    },
    "after": {
        "weekly_status": after.get("status"),
        "weekly_success_at_k_pct": after.get("success_at_k_pct"),
        "weekly_regression_count": after.get("regression_count"),
        "holdout_status": after_holdout.get("status"),
        "holdout_success_at_k_pct": after_holdout.get("success_at_k_pct"),
        "holdout_regression_count": after_holdout.get("regression_count"),
    },
    "delta": {
        "weekly_success_at_k_pct": (
            round(after_success - before_success, 2) if isinstance(before_success, float) and isinstance(after_success, float) else None
        ),
        "weekly_regression_count": (
            round(after_reg - before_reg, 2) if isinstance(before_reg, float) and isinstance(after_reg, float) else None
        ),
        "holdout_success_at_k_pct": (
            round(after_holdout_success - before_holdout_success, 2)
            if isinstance(before_holdout_success, float) and isinstance(after_holdout_success, float)
            else None
        ),
        "holdout_regression_count": (
            round(after_holdout_reg - before_holdout_reg, 2)
            if isinstance(before_holdout_reg, float) and isinstance(after_holdout_reg, float)
            else None
        ),
    },
}

if any(rc != 0 for rc in (before_weekly_rc, after_weekly_rc, before_holdout_rc, after_holdout_rc)):
    payload["status"] = "NEEDS_REVIEW"

out_json.parent.mkdir(parents=True, exist_ok=True)
out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

lines = [
    "# GateForge Agent Modelica MVP Mutant Repair Learning Loop v1",
    "",
    f"- status: `{payload.get('status')}`",
    f"- delta_weekly_success_at_k_pct: `{payload['delta'].get('weekly_success_at_k_pct')}`",
    f"- delta_weekly_regression_count: `{payload['delta'].get('weekly_regression_count')}`",
    f"- delta_holdout_success_at_k_pct: `{payload['delta'].get('holdout_success_at_k_pct')}`",
    f"- delta_holdout_regression_count: `{payload['delta'].get('holdout_regression_count')}`",
    f"- recipe_lock_path: `{payload.get('recipe_lock_path')}`",
    f"- focus_targets_path: `{payload.get('focus_targets_path')}`",
    "",
]
out_md.write_text("\n".join(lines), encoding="utf-8")
print(json.dumps(payload))
PY

cat "$SUMMARY_JSON"
