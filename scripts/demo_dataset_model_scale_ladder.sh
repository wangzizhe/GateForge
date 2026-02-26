#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_model_scale_ladder_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/failure_taxonomy_coverage_summary.json" <<'JSON'
{
  "status": "PASS",
  "model_scale_counts": {"small": 5, "medium": 3, "large": 2}
}
JSON

cat > "$OUT_DIR/failure_distribution_benchmark_summary.json" <<'JSON'
{
  "status": "PASS",
  "distribution": {
    "model_scale_after": {"small": 4, "medium": 2, "large": 1}
  }
}
JSON

python3 -m gateforge.dataset_model_scale_ladder \
  --failure-taxonomy-coverage "$OUT_DIR/failure_taxonomy_coverage_summary.json" \
  --failure-distribution-benchmark "$OUT_DIR/failure_distribution_benchmark_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_model_scale_ladder_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "has_scale_counts": "PASS" if isinstance(payload.get("scale_counts"), dict) else "FAIL",
    "has_ci_recommendation": "PASS" if isinstance(payload.get("ci_recommendation"), dict) else "FAIL",
    "large_ready_present": "PASS" if isinstance(payload.get("large_ready"), bool) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "ladder_status": payload.get("status"),
    "medium_ready": payload.get("medium_ready"),
    "large_ready": payload.get("large_ready"),
    "main_ci_lane_count": len((payload.get("ci_recommendation") or {}).get("main") or []),
    "optional_ci_lane_count": len((payload.get("ci_recommendation") or {}).get("optional") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Model Scale Ladder Demo",
            "",
            f"- ladder_status: `{demo['ladder_status']}`",
            f"- medium_ready: `{demo['medium_ready']}`",
            f"- large_ready: `{demo['large_ready']}`",
            f"- main_ci_lane_count: `{demo['main_ci_lane_count']}`",
            f"- optional_ci_lane_count: `{demo['optional_ci_lane_count']}`",
            f"- bundle_status: `{demo['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "ladder_status": demo["ladder_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
