#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_intake_backlog_prioritizer_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/intake_ledger.json" <<'JSON'
{
  "records": [
    {"model_id": "m1", "decision": "REJECT", "reasons": ["license_not_allowed", "repro_command_missing"]},
    {"model_id": "m2", "decision": "ACCEPT"}
  ]
}
JSON

cat > "$OUT_DIR/license_summary.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "alerts": ["disallowed_license_detected"]
}
JSON

cat > "$OUT_DIR/yield_summary.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "alerts": ["yield_per_accepted_model_below_threshold"]
}
JSON

cat > "$OUT_DIR/matrix_summary.json" <<'JSON'
{
  "missing_cells": [
    {"model_scale": "large", "failure_type": "simulate_error", "missing_mutations": 2}
  ]
}
JSON

python3 -m gateforge.dataset_real_model_intake_backlog_prioritizer_v1 \
  --real-model-intake-ledger "$OUT_DIR/intake_ledger.json" \
  --real-model-license-compliance-summary "$OUT_DIR/license_summary.json" \
  --real-model-failure-yield-summary "$OUT_DIR/yield_summary.json" \
  --mutation-execution-matrix-summary "$OUT_DIR/matrix_summary.json" \
  --backlog-out "$OUT_DIR/backlog.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_real_model_intake_backlog_prioritizer_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
backlog = json.loads((out / "backlog.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "backlog_present": "PASS" if int(summary.get("backlog_item_count", 0) or 0) >= 1 else "FAIL",
    "schema_present": "PASS" if backlog.get("schema_version") == "real_model_intake_backlog_v1" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
owner_lane_coverage = 0
items = backlog.get("items") if isinstance(backlog.get("items"), list) else []
if items:
    owner_lane_coverage = len([x for x in items if isinstance(x, dict) and x.get("owner_lane")]) / len(items)
payload = {
    "backlog_prioritizer_status": summary.get("status"),
    "p0_count": summary.get("p0_count"),
    "owner_lane_coverage_ratio": round(owner_lane_coverage, 2),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "backlog_prioritizer_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
