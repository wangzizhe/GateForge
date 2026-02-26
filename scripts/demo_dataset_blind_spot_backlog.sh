#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_blind_spot_backlog_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/taxonomy.json" <<'JSON'
{"missing_failure_types":["stability_regression"],"missing_model_scales":["large"],"missing_stages":["compile"]}
JSON

cat > "$OUT_DIR/distribution.json" <<'JSON'
{"distribution_drift_score":0.42,"false_positive_rate_after":0.12,"regression_rate_after":0.2}
JSON

cat > "$OUT_DIR/registry_summary.json" <<'JSON'
{"missing_model_scales":["large"],"duplicate_fingerprint_count":2}
JSON

cat > "$OUT_DIR/snapshot.json" <<'JSON'
{"risks":["dataset_failure_distribution_benchmark_needs_review","dataset_model_scale_ladder_needs_review"]}
JSON

python3 -m gateforge.dataset_blind_spot_backlog \
  --failure-taxonomy-coverage "$OUT_DIR/taxonomy.json" \
  --failure-distribution-benchmark "$OUT_DIR/distribution.json" \
  --failure-corpus-registry-summary "$OUT_DIR/registry_summary.json" \
  --snapshot-summary "$OUT_DIR/snapshot.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_blind_spot_backlog_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "tasks_present": "PASS" if isinstance(payload.get("tasks"), list) else "FAIL",
    "priority_counts_present": "PASS" if isinstance(payload.get("priority_counts"), dict) else "FAIL",
    "tasks_non_empty": "PASS" if int(payload.get("total_open_tasks", 0) or 0) > 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "backlog_status": payload.get("status"),
    "total_open_tasks": payload.get("total_open_tasks"),
    "p0_count": (payload.get("priority_counts") or {}).get("P0", 0),
    "p1_count": (payload.get("priority_counts") or {}).get("P1", 0),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Blind Spot Backlog Demo",
            "",
            f"- backlog_status: `{summary['backlog_status']}`",
            f"- total_open_tasks: `{summary['total_open_tasks']}`",
            f"- p0_count: `{summary['p0_count']}`",
            f"- p1_count: `{summary['p1_count']}`",
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
print(json.dumps({"bundle_status": bundle_status, "backlog_status": summary["backlog_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
