#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_corpus_ingest_bridge_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/mutation_manifest.json" <<'JSON'
{
  "schema_version": "mutation_manifest_v1",
  "mutations": [
    {
      "mutation_id": "mut_001",
      "target_model_id": "mdl_probe_large",
      "target_scale": "large",
      "seed": 101,
      "repro_command": "python -m gateforge.run --proposal x"
    },
    {
      "mutation_id": "mut_002",
      "target_model_id": "mdl_probe_medium",
      "target_scale": "medium",
      "seed": 102,
      "repro_command": "python -m gateforge.run --proposal y"
    }
  ]
}
JSON

cat > "$OUT_DIR/stability_summary.json" <<'JSON'
{
  "status": "PASS",
  "unstable_mutations": [
    {"mutation_id": "mut_002"}
  ]
}
JSON

cat > "$OUT_DIR/replay_observations.json" <<'JSON'
{
  "observations": [
    {"mutation_id": "mut_001", "observed_failure_types": ["simulate_error", "simulate_error", "simulate_error"]},
    {"mutation_id": "mut_002", "observed_failure_types": ["semantic_regression", "simulate_error", "semantic_regression"]}
  ]
}
JSON

cat > "$OUT_DIR/existing_db.json" <<'JSON'
{
  "schema_version": "failure_corpus_db_v1",
  "cases": [
    {
      "case_id": "legacy_case_001",
      "fingerprint": "legacy_fp",
      "model_scale": "small",
      "failure_type": "script_parse_error",
      "failure_stage": "compile",
      "severity": "medium",
      "reproducibility": {"simulator_version": "openmodelica-1.25.5", "seed": 1, "scenario_hash": "legacy", "repro_command": "legacy"}
    }
  ]
}
JSON

python3 -m gateforge.dataset_failure_corpus_ingest_bridge_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --repro-stability-summary "$OUT_DIR/stability_summary.json" \
  --replay-observations "$OUT_DIR/replay_observations.json" \
  --existing-failure-corpus-db "$OUT_DIR/existing_db.json" \
  --db-out "$OUT_DIR/db_after.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_failure_corpus_ingest_bridge_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
db_after = json.loads((out / "db_after.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "ingested_present": "PASS" if int(summary.get("ingested_cases", 0) or 0) >= 1 else "FAIL",
    "db_schema_present": "PASS" if db_after.get("schema_version") == "failure_corpus_db_v1" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "ingest_status": summary.get("status"),
    "ingested_cases": summary.get("ingested_cases"),
    "skipped_unstable_cases": summary.get("skipped_unstable_cases"),
    "total_cases_after": summary.get("total_cases_after"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "ingest_status": summary_out["ingest_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
