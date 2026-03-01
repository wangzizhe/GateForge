#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
OUT_DIR="artifacts/dataset_governance_decision_proofbook_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/governance_evidence_pack.json" <<'JSON'
{"status": "PASS"}
JSON
cat > "$OUT_DIR/moat_execution_forecast.json" <<'JSON'
{"status": "PASS", "recommendation": "EXECUTE_BASE_PLAN", "target_gap_pressure_index": 76.5, "model_asset_target_gap_score": 24.0}
JSON
cat > "$OUT_DIR/pack_execution_tracker.json" <<'JSON'
{"status": "NEEDS_REVIEW", "progress_percent": 62.5}
JSON
cat > "$OUT_DIR/policy_experiment_runner.json" <<'JSON'
{"status": "PASS", "recommendation": "RUN_RECOMMENDED"}
JSON

python3 -m gateforge.dataset_governance_decision_proofbook \
  --governance-evidence-pack "$OUT_DIR/governance_evidence_pack.json" \
  --moat-execution-forecast "$OUT_DIR/moat_execution_forecast.json" \
  --pack-execution-tracker "$OUT_DIR/pack_execution_tracker.json" \
  --policy-experiment-runner "$OUT_DIR/policy_experiment_runner.json" \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_governance_decision_proofbook_demo")
p = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if p.get("status") in {"PASS","NEEDS_REVIEW","FAIL"} else "FAIL",
    "decision_present": "PASS" if isinstance(p.get("decision"), str) and p.get("decision") else "FAIL",
    "target_gap_pressure_present": "PASS" if isinstance(p.get("target_gap_pressure_index"), (int, float)) else "FAIL",
}
summary = {
    "proofbook_status": p.get("status"),
    "decision": p.get("decision"),
    "target_gap_pressure_index": p.get("target_gap_pressure_index"),
    "model_asset_target_gap_score": p.get("model_asset_target_gap_score"),
    "result_flags": flags,
    "bundle_status": "PASS" if all(v=="PASS" for v in flags.values()) else "FAIL"
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": summary["bundle_status"], "proofbook_status": summary["proofbook_status"]}))
if summary["bundle_status"] != "PASS":
  raise SystemExit(1)
PY
