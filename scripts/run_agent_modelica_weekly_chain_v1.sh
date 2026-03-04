#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_WEEKLY_CHAIN_OUT_DIR:-artifacts/agent_modelica_weekly_chain_v1}"
WEEK_TAG="${GATEFORGE_AGENT_WEEK_TAG:-$(date -u +%G-W%V)}"
RUN_MODE="${GATEFORGE_AGENT_RUN_MODE:-mock}"
PHYSICS_CONTRACT="${GATEFORGE_AGENT_PHYSICS_CONTRACT:-policies/physics_contract_v0.json}"
PER_SCALE_TOTAL="${GATEFORGE_AGENT_PER_SCALE_TOTAL:-20}"
PER_SCALE_FAILURE_TARGETS="${GATEFORGE_AGENT_PER_SCALE_FAILURE_TARGETS:-7,7,6}"

CORE_MANIFEST="${GATEFORGE_AGENT_CORE_MUTATION_MANIFEST:-}"
SMALL_MANIFEST="${GATEFORGE_AGENT_SMALL_MUTATION_MANIFEST:-}"

if [ -z "$CORE_MANIFEST" ]; then
  if [ -f "artifacts/run_private_model_mutation_scale_batch_v1_demo/batch/mutation_manifest.json" ]; then
    CORE_MANIFEST="artifacts/run_private_model_mutation_scale_batch_v1_demo/batch/mutation_manifest.json"
  elif [ -f "artifacts/run_private_model_mutation_largefirst_sprint_v1_demo/batch/mutation_manifest.json" ]; then
    CORE_MANIFEST="artifacts/run_private_model_mutation_largefirst_sprint_v1_demo/batch/mutation_manifest.json"
  fi
fi

if [ -z "$SMALL_MANIFEST" ]; then
  if [ -f "artifacts/run_modelica_open_source_growth_sprint_v1_demo/growth/scale/mutation_manifest.json" ]; then
    SMALL_MANIFEST="artifacts/run_modelica_open_source_growth_sprint_v1_demo/growth/scale/mutation_manifest.json"
  elif [ -f "artifacts/agent_modelica_taskset_lock_v1_demo/mutation_manifest.json" ]; then
    SMALL_MANIFEST="artifacts/agent_modelica_taskset_lock_v1_demo/mutation_manifest.json"
  fi
fi

if [ -z "$CORE_MANIFEST" ] || [ -z "$SMALL_MANIFEST" ]; then
  echo "Missing manifests. Set GATEFORGE_AGENT_CORE_MUTATION_MANIFEST and GATEFORGE_AGENT_SMALL_MUTATION_MANIFEST." >&2
  exit 1
fi

mkdir -p "$OUT_DIR/tasksets" "$OUT_DIR/baseline" "$OUT_DIR/weekly"
export OUT_DIR

TASKSET_PATH="$OUT_DIR/tasksets/taskset_${WEEK_TAG}.json"
TASKSET_SUMMARY="$OUT_DIR/tasksets/taskset_${WEEK_TAG}_summary.json"

python3 -m gateforge.agent_modelica_taskset_snapshot_v1 \
  --mutation-manifest "$CORE_MANIFEST" \
  --extra-mutation-manifest "$SMALL_MANIFEST" \
  --per-scale-total "$PER_SCALE_TOTAL" \
  --per-scale-failure-targets "$PER_SCALE_FAILURE_TARGETS" \
  --snapshot-version "${WEEK_TAG}" \
  --taskset-out "$TASKSET_PATH" \
  --out "$TASKSET_SUMMARY" \
  --report-out "${TASKSET_SUMMARY%.json}.md"

python3 -m gateforge.agent_modelica_layered_baseline_v1 \
  --taskset-in "$TASKSET_PATH" \
  --run-mode "$RUN_MODE" \
  --physics-contract "$PHYSICS_CONTRACT" \
  --out-dir "$OUT_DIR/baseline" \
  --out "$OUT_DIR/baseline/summary.json" \
  --report-out "$OUT_DIR/baseline/summary.md"

python3 -m gateforge.agent_modelica_weekly_metrics_page_v1 \
  --baseline-summary "$OUT_DIR/baseline/summary.json" \
  --week-tag "$WEEK_TAG" \
  --ledger "$OUT_DIR/weekly/history.jsonl" \
  --out "$OUT_DIR/weekly/page.json" \
  --report-out "$OUT_DIR/weekly/page.md"

python3 - <<'PY'
import json
import os
from pathlib import Path

out_dir = Path(os.environ["OUT_DIR"])
week_page = json.loads((out_dir / "weekly" / "page.json").read_text(encoding="utf-8"))
baseline = json.loads((out_dir / "baseline" / "summary.json").read_text(encoding="utf-8"))
taskset = json.loads((out_dir / "tasksets" / f"taskset_{week_page.get('week_tag')}_summary.json").read_text(encoding="utf-8"))

summary = {
    "week_tag": week_page.get("week_tag"),
    "status": week_page.get("status"),
    "taskset_status": taskset.get("status"),
    "baseline_status": baseline.get("status"),
    "success_at_k_pct": week_page.get("success_at_k_pct"),
    "median_time_to_pass_sec": week_page.get("median_time_to_pass_sec"),
    "median_repair_rounds": week_page.get("median_repair_rounds"),
    "regression_count": week_page.get("regression_count"),
    "physics_fail_count": week_page.get("physics_fail_count"),
    "layered_pass_rate_pct_by_scale": week_page.get("layered_pass_rate_pct_by_scale"),
    "top_fail_reasons": week_page.get("top_fail_reasons"),
}
(out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary))
if str(week_page.get("status") or "") == "FAIL":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
