#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_label_calibrator_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/mutation_manifest.json" <<'JSON'
{
  "schema_version": "mutation_manifest_v1",
  "mutations": [
    {"mutation_id": "mut_001", "target_model_id": "PlantA", "target_scale": "medium", "expected_failure_type": "simulate_error"},
    {"mutation_id": "mut_002", "target_model_id": "PlantB", "target_scale": "large", "expected_failure_type": "model_check_error"},
    {"mutation_id": "mut_003", "target_model_id": "PlantC", "target_scale": "small", "expected_failure_type": "semantic_regression"}
  ]
}
JSON

cat > "$OUT_DIR/raw_observations.json" <<'JSON'
{
  "schema_version": "mutation_raw_observations_v1",
  "observations": [
    {
      "mutation_id": "mut_001",
      "target_model_id": "PlantA",
      "target_scale": "medium",
      "attempts": [{"return_code": 2, "timed_out": false, "stderr": "solver failed during simulation"}]
    },
    {
      "mutation_id": "mut_002",
      "target_model_id": "PlantB",
      "target_scale": "large",
      "attempts": [{"return_code": 1, "timed_out": false, "stderr": "model check type mismatch"}]
    },
    {
      "mutation_id": "mut_003",
      "target_model_id": "PlantC",
      "target_scale": "small",
      "attempts": [{"return_code": 0, "timed_out": false, "stdout": "ok", "stderr": ""}]
    }
  ]
}
JSON

python3 -m gateforge.dataset_failure_label_calibrator_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --raw-observations "$OUT_DIR/raw_observations.json" \
  --replay-observations-out "$OUT_DIR/replay_observations.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_failure_label_calibrator_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
replay = json.loads((out / "replay_observations.json").read_text(encoding="utf-8"))
rows = replay.get("observations") if isinstance(replay.get("observations"), list) else []
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "replay_rows_present": "PASS" if len(rows) >= 3 else "FAIL",
    "match_ratio_present": "PASS" if summary.get("expected_match_ratio_pct") is not None else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "calibrator_status": summary.get("status"),
    "expected_match_ratio_pct": summary.get("expected_match_ratio_pct"),
    "low_confidence_count": summary.get("low_confidence_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "calibrator_status": payload["calibrator_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
