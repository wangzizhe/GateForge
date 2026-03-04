#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/agent_modelica_taskset_lock_v1_demo"
mkdir -p "$OUT_DIR"

cat > "$OUT_DIR/mutation_manifest.json" <<'JSON'
{
  "mutations": [
    {"mutation_id":"m_small_1","target_scale":"small","expected_failure_type":"model_check_error","source_model_path":"a.mo","mutated_model_path":"a1.mo","repro_command":"echo ok"},
    {"mutation_id":"m_medium_1","target_scale":"medium","expected_failure_type":"simulate_error","source_model_path":"b.mo","mutated_model_path":"b1.mo","repro_command":"echo ok"},
    {"mutation_id":"m_large_1","target_scale":"large","expected_failure_type":"semantic_regression","source_model_path":"c.mo","mutated_model_path":"c1.mo","repro_command":"echo ok"}
  ]
}
JSON

python3 -m gateforge.agent_modelica_taskset_lock_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --max-per-scale 5 \
  --taskset-out "$OUT_DIR/taskset.json" \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
p = Path("artifacts/agent_modelica_taskset_lock_v1_demo/summary.json")
taskset = Path("artifacts/agent_modelica_taskset_lock_v1_demo/taskset.json")
s = json.loads(p.read_text(encoding="utf-8"))
t = json.loads(taskset.read_text(encoding="utf-8"))
flags = {
    "status_pass_or_review": "PASS" if s.get("status") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
    "tasks_nonzero": "PASS" if int(s.get("total_tasks", 0)) > 0 else "FAIL",
    "taskset_rows_match": "PASS" if len(t.get("tasks", [])) == int(s.get("total_tasks", 0)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {"bundle_status": bundle_status, "flags": flags}
print(json.dumps(payload))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

