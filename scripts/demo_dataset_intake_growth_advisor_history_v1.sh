#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_intake_growth_advisor_history_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

cat > "$OUT_DIR/r1.json" <<'JSON'
{"status":"PASS","advice":{"suggested_action":"keep","priority":"P3","confidence":0.62,"backlog_actions":[]}}
JSON

cat > "$OUT_DIR/r2.json" <<'JSON'
{"status":"NEEDS_REVIEW","advice":{"suggested_action":"execute_targeted_growth_patch","priority":"P1","confidence":0.78,"backlog_actions":[{"action_id":"a1"},{"action_id":"a2"}]}}
JSON

python3 -m gateforge.dataset_intake_growth_advisor_history_v1 \
  --record "$OUT_DIR/r1.json" \
  --record "$OUT_DIR/r2.json" \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_intake_growth_advisor_history_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "total_records_present": "PASS" if isinstance(summary.get("total_records"), int) else "FAIL",
    "latest_action_present": "PASS" if isinstance(summary.get("latest_suggested_action"), (str, type(None))) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "history_status": summary.get("status"),
    "total_records": summary.get("total_records"),
    "latest_suggested_action": summary.get("latest_suggested_action"),
    "recovery_plan_rate": summary.get("recovery_plan_rate"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "history_status": demo["history_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
