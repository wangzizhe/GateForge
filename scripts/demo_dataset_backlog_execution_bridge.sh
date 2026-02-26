#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_backlog_execution_bridge_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/backlog_summary.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "total_open_tasks": 4,
  "tasks": [
    {"task_id": "blindspot.failure_type.stability_regression", "title": "Add failure type coverage", "reason": "taxonomy_missing_failure_type", "priority": "P1"},
    {"task_id": "blindspot.model_scale.large", "title": "Expand large coverage", "reason": "taxonomy_missing_model_scale", "priority": "P0"},
    {"task_id": "blindspot.distribution_drift", "title": "Reduce drift", "reason": "distribution_drift_exceeds_threshold", "priority": "P1"}
  ]
}
JSON

python3 -m gateforge.dataset_backlog_execution_bridge \
  --backlog-summary "$OUT_DIR/backlog_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_backlog_execution_bridge_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "tasks_present": "PASS" if isinstance(payload.get("execution_tasks"), list) else "FAIL",
    "ready_count_present": "PASS" if isinstance(payload.get("ready_count"), int) else "FAIL",
    "non_empty": "PASS" if int(payload.get("total_execution_tasks", 0) or 0) > 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "bridge_status": payload.get("status"),
    "total_execution_tasks": payload.get("total_execution_tasks"),
    "ready_count": payload.get("ready_count"),
    "blocked_count": payload.get("blocked_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Backlog Execution Bridge Demo",
            "",
            f"- bridge_status: `{summary['bridge_status']}`",
            f"- total_execution_tasks: `{summary['total_execution_tasks']}`",
            f"- ready_count: `{summary['ready_count']}`",
            f"- blocked_count: `{summary['blocked_count']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "bridge_status": summary["bridge_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
