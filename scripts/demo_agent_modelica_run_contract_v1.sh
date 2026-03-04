#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/agent_modelica_run_contract_v1_demo"
mkdir -p "$OUT_DIR"

cat > "$OUT_DIR/taskset.json" <<'JSON'
{
  "tasks": [
    {"task_id":"t1","scale":"small","failure_type":"model_check_error","mock_success_round":2,"mock_round_duration_sec":20},
    {"task_id":"t2","scale":"medium","failure_type":"simulate_error","mock_success_round":3,"mock_round_duration_sec":30},
    {"task_id":"t3","scale":"large","failure_type":"semantic_regression","mock_success_round":2,"mock_round_duration_sec":40}
  ]
}
JSON

python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset "$OUT_DIR/taskset.json" \
  --max-rounds 5 \
  --max-time-sec 300 \
  --results-out "$OUT_DIR/results.json" \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
s = json.loads(Path("artifacts/agent_modelica_run_contract_v1_demo/summary.json").read_text(encoding="utf-8"))
r = json.loads(Path("artifacts/agent_modelica_run_contract_v1_demo/results.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if s.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "records_present": "PASS" if len(r.get("records", [])) == 3 else "FAIL",
    "success_positive": "PASS" if int(s.get("success_count", 0)) > 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {"bundle_status": bundle_status, "flags": flags}
print(json.dumps(payload))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

