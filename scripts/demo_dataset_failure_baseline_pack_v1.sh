#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_baseline_pack_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/db.json" <<'JSON'
{
  "schema_version": "failure_corpus_db_v1",
  "cases": [
    {"case_id": "c1", "model_scale": "small", "failure_type": "a", "failure_stage": "simulation", "severity": "low", "fingerprint": "f1", "reproducibility": {"simulator_version": "x", "seed": 1, "scenario_hash": "s", "repro_command": "r"}},
    {"case_id": "c2", "model_scale": "small", "failure_type": "b", "failure_stage": "simulation", "severity": "low", "fingerprint": "f2", "reproducibility": {"simulator_version": "x", "seed": 1, "scenario_hash": "s", "repro_command": "r"}},
    {"case_id": "c3", "model_scale": "medium", "failure_type": "c", "failure_stage": "simulation", "severity": "medium", "fingerprint": "f3", "reproducibility": {"simulator_version": "x", "seed": 1, "scenario_hash": "s", "repro_command": "r"}},
    {"case_id": "c4", "model_scale": "medium", "failure_type": "d", "failure_stage": "simulation", "severity": "high", "fingerprint": "f4", "reproducibility": {"simulator_version": "x", "seed": 1, "scenario_hash": "s", "repro_command": "r"}},
    {"case_id": "c5", "model_scale": "large", "failure_type": "e", "failure_stage": "simulation", "severity": "high", "fingerprint": "f5", "reproducibility": {"simulator_version": "x", "seed": 1, "scenario_hash": "s", "repro_command": "r"}},
    {"case_id": "c6", "model_scale": "large", "failure_type": "f", "failure_stage": "postprocess", "severity": "critical", "fingerprint": "f6", "reproducibility": {"simulator_version": "x", "seed": 1, "scenario_hash": "s", "repro_command": "r"}}
  ]
}
JSON

python3 -m gateforge.dataset_failure_baseline_pack_v1 \
  --failure-corpus-db "$OUT_DIR/db.json" \
  --small-quota 2 \
  --medium-quota 2 \
  --large-quota 2 \
  --pack-out "$OUT_DIR/pack.json" \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_failure_baseline_pack_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
pack = json.loads((out / "pack.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "pack_schema_present": "PASS" if pack.get("schema_version") == "failure_baseline_pack_v1" else "FAIL",
    "selected_cases_present": "PASS" if int(summary.get("total_selected_cases", 0) or 0) > 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "baseline_status": summary.get("status"),
    "total_selected_cases": summary.get("total_selected_cases"),
    "scale_counts": summary.get("scale_counts"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "baseline_status": summary_out["baseline_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
