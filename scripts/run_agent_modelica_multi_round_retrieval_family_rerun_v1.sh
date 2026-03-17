#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_MULTI_ROUND_FAILURE_LIVE_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_multi_round_failure_live_evidence_v1}"
SOURCE_RUN_ID="${GATEFORGE_AGENT_MULTI_ROUND_SOURCE_RUN_ID:-multi_round_live_baseline_04}"
FAMILY="${GATEFORGE_AGENT_MULTI_ROUND_RETRIEVAL_FAMILY:-coupled_conflict_failure}"
RUN_ID="${GATEFORGE_AGENT_MULTI_ROUND_FAILURE_RUN_ID:-${SOURCE_RUN_ID}_${FAMILY}_retrieval_rerun}"
SOURCE_RUN_ROOT="${GATEFORGE_AGENT_MULTI_ROUND_SOURCE_RUN_ROOT:-$OUT_DIR/runs/$SOURCE_RUN_ID}"
RUN_ROOT="${GATEFORGE_AGENT_MULTI_ROUND_FAILURE_RUN_ROOT:-$OUT_DIR/runs/$RUN_ID}"
PREPARE_ONLY="${GATEFORGE_AGENT_MULTI_ROUND_FAMILY_RERUN_PREPARE_ONLY:-0}"

mkdir -p "$RUN_ROOT"

python3 - "$SOURCE_RUN_ROOT" "$RUN_ROOT" "$RUN_ID" "$FAMILY" <<'PY'
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

source_root = Path(sys.argv[1])
run_root = Path(sys.argv[2])
run_id = sys.argv[3]
family = sys.argv[4].strip().lower()

challenge_root = run_root / "challenge"
curated_root = run_root / "curated_retrieval"
baseline_root = run_root / "baseline_off_live"
det_root = run_root / "deterministic_on_live"
retrieval_root = run_root / "retrieval_on_live"
for p in (challenge_root, curated_root, baseline_root, det_root, retrieval_root):
    p.mkdir(parents=True, exist_ok=True)

taskset = json.loads((source_root / "challenge" / "taskset_frozen.json").read_text(encoding="utf-8"))
tasks = [row for row in (taskset.get("tasks") or []) if isinstance(row, dict)]
filtered_tasks = [row for row in tasks if str(row.get("failure_type") or "").strip().lower() == family]
task_ids = {str(row.get("task_id") or "").strip() for row in filtered_tasks}
if not filtered_tasks:
    raise SystemExit(f"no tasks found for family: {family}")

def _library_id(task: dict) -> str:
    source_meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
    return str(task.get("library_id") or source_meta.get("library_id") or "unknown").strip().lower()

counts_by_library = Counter(_library_id(task) for task in filtered_tasks)
counts_by_failure_type = Counter(str(task.get("failure_type") or "unknown").strip().lower() for task in filtered_tasks)
counts_by_multi_round_family = Counter(str(task.get("multi_round_family") or "unknown").strip().lower() for task in filtered_tasks)
counts_by_expected_rounds_min = Counter(str(task.get("expected_rounds_min") or "unknown").strip() for task in filtered_tasks)
cascade_depth_distribution = Counter(str(task.get("cascade_depth") or "unknown").strip() for task in filtered_tasks)

(challenge_root / "taskset_frozen.json").write_text(json.dumps({"tasks": filtered_tasks}, indent=2), encoding="utf-8")
manifest_path = source_root / "challenge" / "manifest.json"
if manifest_path.exists():
    (challenge_root / "manifest.json").write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
unfrozen_path = source_root / "challenge" / "taskset_unfrozen.json"
if unfrozen_path.exists():
    (challenge_root / "taskset_unfrozen.json").write_text(unfrozen_path.read_text(encoding="utf-8"), encoding="utf-8")
challenge_summary = {
    "status": "PASS",
    "total_tasks": len(filtered_tasks),
    "taskset_frozen_path": str(challenge_root / "taskset_frozen.json"),
    "counts_by_library": dict(counts_by_library),
    "counts_by_failure_type": dict(counts_by_failure_type),
    "counts_by_multi_round_family": dict(counts_by_multi_round_family),
    "counts_by_expected_rounds_min": dict(counts_by_expected_rounds_min),
    "cascade_depth_distribution": dict(cascade_depth_distribution),
}
(challenge_root / "summary.json").write_text(json.dumps(challenge_summary, indent=2), encoding="utf-8")

for name in ("history.json", "summary.json"):
    src = source_root / "curated_retrieval" / name
    if src.exists():
        (curated_root / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
for name in ("merged_repair_history.json", "easy_task_exclusions.json"):
    src = source_root / name
    if src.exists():
        (run_root / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

def _filter_results(src_path: Path, dest_path: Path) -> dict:
    payload = json.loads(src_path.read_text(encoding="utf-8"))
    records = [row for row in (payload.get("records") or []) if isinstance(row, dict) and str(row.get("task_id") or "").strip() in task_ids]
    out = dict(payload)
    out["records"] = records
    dest_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out

def _median(values):
    if not values:
        return 0.0
    values = sorted(values)
    mid = len(values) // 2
    if len(values) % 2:
        return float(values[mid])
    return float((values[mid - 1] + values[mid]) / 2.0)

def _summary_from_results(results_payload: dict) -> dict:
    records = [row for row in (results_payload.get("records") or []) if isinstance(row, dict)]
    success_count = sum(1 for row in records if bool(row.get("passed")))
    time_values = [float(row.get("time_to_pass_sec") or 0.0) for row in records if bool(row.get("passed"))]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if success_count == len(records) else "NEEDS_REVIEW",
        "total_tasks": len(records),
        "success_count": success_count,
        "success_at_k_pct": round((success_count / len(records)) * 100.0, 2) if records else 0.0,
        "median_time_to_pass_sec": round(_median(time_values), 2),
    }

baseline_results = _filter_results(source_root / "baseline_off_live" / "results.json", baseline_root / "results.json")
(baseline_root / "summary.json").write_text(json.dumps(_summary_from_results(baseline_results), indent=2), encoding="utf-8")

det_results = _filter_results(source_root / "deterministic_on_live" / "results.json", det_root / "results.json")
(det_root / "summary.json").write_text(json.dumps(_summary_from_results(det_results), indent=2), encoding="utf-8")

baseline_summary_src = source_root / "multi_round_baseline_summary.json"
baseline_summary_out = run_root / "multi_round_baseline_summary.json"
cmd_summary = {
    "challenge_summary": str(challenge_root / "summary.json"),
    "baseline_summary": str(baseline_root / "summary.json"),
    "baseline_results": str(baseline_root / "results.json"),
    "out": str(baseline_summary_out),
}
from subprocess import run
proc = run(
    [
        sys.executable,
        "-m",
        "gateforge.agent_modelica_multi_round_baseline_summary_v1",
        "--challenge-summary",
        cmd_summary["challenge_summary"],
        "--baseline-summary",
        cmd_summary["baseline_summary"],
        "--baseline-results",
        cmd_summary["baseline_results"],
        "--out",
        cmd_summary["out"],
    ],
    check=False,
)
if proc.returncode != 0 and not baseline_summary_out.exists():
    raise SystemExit(proc.returncode)

run_manifest = {
    "schema_version": "agent_modelica_multi_round_live_run_manifest_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_id": run_id,
    "run_root": str(run_root),
    "manifest_path": str((source_root / "run_manifest.json").resolve()) if (source_root / "run_manifest.json").exists() else "",
    "family_filter": family,
    "source_run_root": str(source_root),
}
(run_root / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

def _stage_status(stage: str, summary_path: Path) -> dict:
    return {
        "schema_version": "agent_modelica_multi_round_live_stage_status_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "status": "PASS",
        "exit_code": 0,
        "summary_path": str(summary_path),
        "complete": True,
    }

stages = {
    "challenge": challenge_root / "summary.json",
    "curated_retrieval": curated_root / "summary.json",
    "baseline_off_live": baseline_root / "summary.json",
    "multi_round_baseline_summary": baseline_summary_out,
    "deterministic_on_live": det_root / "summary.json",
}
for stage, summary_path in stages.items():
    stage_path = run_root / "stages" / stage / "stage_status.json"
    stage_path.parent.mkdir(parents=True, exist_ok=True)
    stage_path.write_text(json.dumps(_stage_status(stage, summary_path), indent=2), encoding="utf-8")
PY

if [ "$PREPARE_ONLY" = "1" ]; then
  echo "{\"status\":\"PASS\",\"run_id\":\"$RUN_ID\",\"run_root\":\"$RUN_ROOT\",\"family\":\"$FAMILY\"}"
  exit 0
fi

unset GATEFORGE_AGENT_MULTI_ROUND_FAILURE_STOP_AFTER_STAGE
export GATEFORGE_AGENT_MULTI_ROUND_FAILURE_RESUME=1
export GATEFORGE_AGENT_MULTI_ROUND_FAILURE_RUN_ID="$RUN_ID"
export GATEFORGE_AGENT_MULTI_ROUND_FAILURE_RUN_ROOT="$RUN_ROOT"

bash scripts/run_agent_modelica_multi_round_failure_live_evidence_v1.sh
