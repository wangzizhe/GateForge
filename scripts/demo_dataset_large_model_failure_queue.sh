#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_large_model_failure_queue_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/blind_spot_backlog.json" <<'JSON'
{
  "tasks": [
    {"task_id": "blindspot.model_scale.large", "title": "Expand large coverage", "reason": "taxonomy_missing_model_scale", "priority": "P0"},
    {"task_id": "blindspot.regression_rate", "title": "Mitigate regression", "reason": "regression_rate_high", "priority": "P0"},
    {"task_id": "blindspot.model_scale.medium", "title": "Expand medium coverage", "reason": "taxonomy_missing_model_scale", "priority": "P1"}
  ]
}
JSON

cat > "$OUT_DIR/failure_corpus_registry_summary.json" <<'JSON'
{
  "missing_model_scales": ["large"]
}
JSON

python3 -m gateforge.dataset_large_model_failure_queue \
  --blind-spot-backlog "$OUT_DIR/blind_spot_backlog.json" \
  --failure-corpus-registry-summary "$OUT_DIR/failure_corpus_registry_summary.json" \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_large_model_failure_queue_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "queue_present": "PASS" if isinstance(payload.get("queue"), list) else "FAIL",
    "has_item": "PASS" if int(payload.get("total_queue_items", 0)) > 0 else "FAIL",
}
summary = {"queue_status": payload.get("status"), "total_queue_items": payload.get("total_queue_items"), "result_flags": flags, "bundle_status": "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": summary["bundle_status"], "queue_status": summary["queue_status"]}))
if summary["bundle_status"] != "PASS":
    raise SystemExit(1)
PY
