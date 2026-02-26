#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_pack_execution_tracker_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/modelica_failure_pack_plan.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "total_target_new_cases": 15,
  "scale_plan": [
    {"scale": "large", "target_new_cases": 4},
    {"scale": "medium", "target_new_cases": 6},
    {"scale": "small", "target_new_cases": 5}
  ]
}
JSON

cat > "$OUT_DIR/executed_summary.json" <<'JSON'
{
  "completed_cases": 8,
  "blocked_cases": 1,
  "scale_completed": {"large": 1, "medium": 4, "small": 3}
}
JSON

python3 -m gateforge.dataset_pack_execution_tracker \
  --modelica-failure-pack-plan "$OUT_DIR/modelica_failure_pack_plan.json" \
  --executed-summary "$OUT_DIR/executed_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_pack_execution_tracker_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "progress_present": "PASS" if isinstance(payload.get("progress_percent"), (int, float)) else "FAIL",
    "large_progress_present": "PASS" if isinstance(payload.get("large_scale_progress_percent"), (int, float)) else "FAIL",
}
summary = {
    "tracker_status": payload.get("status"),
    "progress_percent": payload.get("progress_percent"),
    "large_scale_progress_percent": payload.get("large_scale_progress_percent"),
    "result_flags": flags,
    "bundle_status": "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL",
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": summary["bundle_status"], "tracker_status": summary["tracker_status"]}))
if summary["bundle_status"] != "PASS":
    raise SystemExit(1)
PY
