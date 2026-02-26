#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_modelica_failure_pack_planner_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/failure_coverage_planner.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "plan": [
    {
      "plan_id": "coverage.plan.001",
      "source_task_id": "blindspot.model_scale.large",
      "priority": "P0",
      "focus": "taxonomy_missing_model_scale",
      "size_hint": "large",
      "expected_moat_delta": 8.5
    },
    {
      "plan_id": "coverage.plan.002",
      "source_task_id": "blindspot.failure_type.numerical_divergence",
      "priority": "P1",
      "focus": "taxonomy_missing_failure_type",
      "size_hint": "medium",
      "expected_moat_delta": 5.8
    }
  ]
}
JSON

cat > "$OUT_DIR/model_scale_ladder.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "scale_counts": {
    "small": 6,
    "medium": 2,
    "large": 0
  }
}
JSON

cat > "$OUT_DIR/failure_corpus_registry_summary.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "model_scale_counts": {
    "small": 12,
    "medium": 4,
    "large": 1
  }
}
JSON

python3 -m gateforge.dataset_modelica_failure_pack_planner \
  --failure-coverage-planner "$OUT_DIR/failure_coverage_planner.json" \
  --model-scale-ladder "$OUT_DIR/model_scale_ladder.json" \
  --failure-corpus-registry-summary "$OUT_DIR/failure_corpus_registry_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_modelica_failure_pack_planner_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "scale_plan_present": "PASS" if isinstance(payload.get("scale_plan"), list) and len(payload.get("scale_plan")) == 3 else "FAIL",
    "medium_large_targets": "PASS" if int(payload.get("medium_target_new_cases", 0) or 0) >= 1 and int(payload.get("large_target_new_cases", 0) or 0) >= 1 else "FAIL",
    "total_target_present": "PASS" if int(payload.get("total_target_new_cases", 0) or 0) >= 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "planner_status": payload.get("status"),
    "total_target_new_cases": payload.get("total_target_new_cases"),
    "medium_target_new_cases": payload.get("medium_target_new_cases"),
    "large_target_new_cases": payload.get("large_target_new_cases"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Modelica Failure Pack Planner Demo",
            "",
            f"- planner_status: `{summary['planner_status']}`",
            f"- total_target_new_cases: `{summary['total_target_new_cases']}`",
            f"- medium_target_new_cases: `{summary['medium_target_new_cases']}`",
            f"- large_target_new_cases: `{summary['large_target_new_cases']}`",
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
