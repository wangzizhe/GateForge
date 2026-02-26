#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_large_coverage_push_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/failure_corpus_db.json" <<'JSON'
{
  "schema_version": "failure_corpus_db_v1",
  "cases": [
    {"case_id": "c001", "model_scale": "small", "failure_type": "simulate_error"},
    {"case_id": "c002", "model_scale": "small", "failure_type": "model_check_error"},
    {"case_id": "c003", "model_scale": "medium", "failure_type": "semantic_regression"},
    {"case_id": "c004", "model_scale": "large", "failure_type": "simulate_error"}
  ]
}
JSON

cat > "$OUT_DIR/model_scale_ladder_summary.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "large_ready": false
}
JSON

cat > "$OUT_DIR/large_model_failure_queue.json" <<'JSON'
{
  "queue": [
    {"queue_id": "largeq.001", "priority": "P0", "reason": "registry_missing_model_scale"},
    {"queue_id": "largeq.002", "priority": "P1", "reason": "distribution_drift"}
  ]
}
JSON

python3 -m gateforge.dataset_large_coverage_push_v1 \
  --failure-corpus-db "$OUT_DIR/failure_corpus_db.json" \
  --model-scale-ladder-summary "$OUT_DIR/model_scale_ladder_summary.json" \
  --large-model-failure-queue "$OUT_DIR/large_model_failure_queue.json" \
  --target-large-share-pct 30 \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_large_coverage_push_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
actions = summary.get("recommended_actions") if isinstance(summary.get("recommended_actions"), list) else []
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "target_present": "PASS" if int(summary.get("push_target_large_cases", 0) or 0) >= 1 else "FAIL",
    "actions_present": "PASS" if len(actions) >= 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "push_status": summary.get("status"),
    "current_large_share_pct": summary.get("current_large_share_pct"),
    "push_target_large_cases": summary.get("push_target_large_cases"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "push_status": payload["push_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
