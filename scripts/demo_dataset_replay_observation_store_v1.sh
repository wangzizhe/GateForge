#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_replay_observation_store_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

cat > "$OUT_DIR/raw_observations.json" <<'JSON'
{
  "schema_version": "mutation_raw_observations_v1",
  "observations": [
    {
      "mutation_id": "m1",
      "target_model_id": "mdl_a",
      "target_scale": "medium",
      "execution_status": "EXECUTED",
      "attempt_count": 1,
      "repro_command": "python3 -c \"print('ok')\"",
      "attempts": [{"return_code": 0, "timed_out": false, "exception": "", "duration_sec": 0.1, "stdout": "ok", "stderr": ""}]
    },
    {
      "mutation_id": "m2",
      "target_model_id": "mdl_b",
      "target_scale": "large",
      "execution_status": "EXECUTED",
      "attempt_count": 1,
      "repro_command": "python3 -c \"import sys; sys.exit(2)\"",
      "attempts": [{"return_code": 2, "timed_out": false, "exception": "", "duration_sec": 0.1, "stdout": "", "stderr": ""}]
    }
  ]
}
JSON

python3 -m gateforge.dataset_replay_observation_store_v1 \
  --raw-observations "$OUT_DIR/raw_observations.json" \
  --store-path "$OUT_DIR/observations.jsonl" \
  --run-id "demo_run_001" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_replay_observation_store_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
lines = [x for x in (out / "observations.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "ingested_present": "PASS" if int(summary.get("ingested_records", 0) or 0) >= 1 else "FAIL",
    "store_lines_present": "PASS" if len(lines) >= 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "store_status": summary.get("status"),
    "ingested_records": summary.get("ingested_records"),
    "total_store_records": summary.get("total_store_records"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "store_status": summary_out["store_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
