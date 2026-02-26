#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_coverage_planner_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/blind_spot_backlog.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "total_open_tasks": 4,
  "tasks": [
    {
      "task_id": "blindspot.model_scale.large",
      "title": "Expand model scale coverage: large",
      "reason": "taxonomy_missing_model_scale",
      "priority": "P0"
    },
    {
      "task_id": "blindspot.failure_type.solver_non_convergence",
      "title": "Add failure type coverage: solver_non_convergence",
      "reason": "taxonomy_missing_failure_type",
      "priority": "P1"
    },
    {
      "task_id": "blindspot.distribution_drift",
      "title": "Rebalance failure distribution benchmark",
      "reason": "distribution_drift_exceeds_threshold",
      "priority": "P1"
    }
  ]
}
JSON

cat > "$OUT_DIR/failure_corpus_registry_summary.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "total_records": 27,
  "missing_model_scales": ["large"]
}
JSON

cat > "$OUT_DIR/moat_trend_snapshot.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "metrics": {
    "moat_score": 58.3
  }
}
JSON

python3 -m gateforge.dataset_failure_coverage_planner \
  --blind-spot-backlog "$OUT_DIR/blind_spot_backlog.json" \
  --failure-corpus-registry-summary "$OUT_DIR/failure_corpus_registry_summary.json" \
  --moat-trend-snapshot "$OUT_DIR/moat_trend_snapshot.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_failure_coverage_planner_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "plan_present": "PASS" if isinstance(payload.get("plan"), list) else "FAIL",
    "has_items": "PASS" if int(payload.get("total_plan_items", 0) or 0) >= 1 else "FAIL",
    "moat_delta_present": "PASS" if isinstance(payload.get("expected_moat_delta_total"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "planner_status": payload.get("status"),
    "total_plan_items": payload.get("total_plan_items"),
    "ready_large_model_tracks": payload.get("ready_large_model_tracks"),
    "expected_moat_delta_total": payload.get("expected_moat_delta_total"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Failure Coverage Planner Demo",
            "",
            f"- planner_status: `{summary['planner_status']}`",
            f"- total_plan_items: `{summary['total_plan_items']}`",
            f"- ready_large_model_tracks: `{summary['ready_large_model_tracks']}`",
            f"- expected_moat_delta_total: `{summary['expected_moat_delta_total']}`",
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
print(json.dumps({"bundle_status": bundle_status, "planner_status": summary["planner_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
