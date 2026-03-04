#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/agent_modelica_acceptance_gate_v1_demo"
mkdir -p "$OUT_DIR"

cat > "$OUT_DIR/run_results.json" <<'JSON'
{
  "records": [
    {
      "task_id": "t1",
      "scale": "small",
      "rounds_used": 2,
      "elapsed_sec": 80,
      "hard_checks": {
        "check_model_pass": true,
        "simulate_pass": true,
        "physics_contract_pass": true,
        "regression_pass": true
      }
    },
    {
      "task_id": "t2",
      "scale": "medium",
      "rounds_used": 6,
      "elapsed_sec": 360,
      "hard_checks": {
        "check_model_pass": true,
        "simulate_pass": true,
        "physics_contract_pass": true,
        "regression_pass": true
      }
    }
  ]
}
JSON

python3 -m gateforge.agent_modelica_acceptance_gate_v1 \
  --run-results "$OUT_DIR/run_results.json" \
  --small-max-time-sec 300 \
  --medium-max-time-sec 300 \
  --small-max-rounds 5 \
  --medium-max-rounds 5 \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
s = json.loads(Path("artifacts/agent_modelica_acceptance_gate_v1_demo/summary.json").read_text(encoding="utf-8"))
flags = {
    "status_expected_review": "PASS" if s.get("status") == "NEEDS_REVIEW" else "FAIL",
    "verdicts_present": "PASS" if len(s.get("verdicts", [])) == 2 else "FAIL",
    "needs_review_positive": "PASS" if int(s.get("needs_review_count", 0)) > 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {"bundle_status": bundle_status, "flags": flags}
print(json.dumps(payload))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

