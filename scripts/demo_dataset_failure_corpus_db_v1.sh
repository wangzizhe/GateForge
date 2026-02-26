#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_corpus_db_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/registry.json" <<'JSON'
[
  {
    "corpus_case_id": "fc-a001",
    "fingerprint": "abc123",
    "model_scale": "small",
    "failure_type": "solver_non_convergence",
    "failure_stage": "simulation",
    "severity": "medium",
    "model_name": "PumpA"
  },
  {
    "corpus_case_id": "fc-a002",
    "fingerprint": "def456",
    "model_scale": "large",
    "failure_type": "stability_regression",
    "failure_stage": "postprocess",
    "severity": "high",
    "model_name": "GridB"
  }
]
JSON

cat > "$OUT_DIR/repro_defaults.json" <<'JSON'
{
  "simulator_version": "openmodelica-1.25.5",
  "seed": 42,
  "scenario_hash": "demo-scenario-v1",
  "repro_command": "python -m gateforge.run --proposal <id>"
}
JSON

python3 -m gateforge.dataset_failure_corpus_db_v1 \
  --failure-corpus-registry "$OUT_DIR/registry.json" \
  --repro-defaults "$OUT_DIR/repro_defaults.json" \
  --db-out "$OUT_DIR/db.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_failure_corpus_db_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
db = json.loads((out / "db.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "schema_present": "PASS" if db.get("schema_version") == "failure_corpus_db_v1" else "FAIL",
    "cases_present": "PASS" if isinstance(db.get("cases"), list) and len(db.get("cases")) > 0 else "FAIL",
    "repro_present": "PASS" if isinstance((db.get("cases") or [{}])[0].get("reproducibility"), dict) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "db_status": summary.get("status"),
    "total_cases": summary.get("total_cases"),
    "completeness_ratio_pct": summary.get("completeness_ratio_pct"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "db_status": summary_out["db_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
