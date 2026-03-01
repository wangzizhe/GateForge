#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
OUT_DIR="artifacts/dataset_governance_evidence_release_manifest_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/governance_decision_proofbook.json" <<'JSON'
{"status": "PASS"}
JSON
cat > "$OUT_DIR/moat_execution_forecast.json" <<'JSON'
{"status": "PASS", "target_gap_pressure_index": 76.5, "model_asset_target_gap_score": 28.5}
JSON
cat > "$OUT_DIR/model_scale_mix_guard.json" <<'JSON'
{"status": "NEEDS_REVIEW"}
JSON
cat > "$OUT_DIR/failure_supply_plan.json" <<'JSON'
{"status": "NEEDS_REVIEW"}
JSON

python3 -m gateforge.dataset_governance_evidence_release_manifest \
  --governance-decision-proofbook "$OUT_DIR/governance_decision_proofbook.json" \
  --moat-execution-forecast "$OUT_DIR/moat_execution_forecast.json" \
  --model-scale-mix-guard "$OUT_DIR/model_scale_mix_guard.json" \
  --failure-supply-plan "$OUT_DIR/failure_supply_plan.json" \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_governance_evidence_release_manifest_demo")
p = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if p.get("status") in {"PASS","NEEDS_REVIEW","FAIL"} else "FAIL",
    "release_ready_present": "PASS" if isinstance(p.get("release_ready"), bool) else "FAIL",
    "target_gap_pressure_present": "PASS" if isinstance(p.get("target_gap_pressure_index"), (int,float)) else "FAIL",
}
summary = {
    "manifest_status": p.get("status"),
    "release_ready": p.get("release_ready"),
    "target_gap_pressure_index": p.get("target_gap_pressure_index"),
    "model_asset_target_gap_score": p.get("model_asset_target_gap_score"),
    "result_flags": flags,
    "bundle_status": "PASS" if all(v=="PASS" for v in flags.values()) else "FAIL"
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": summary["bundle_status"], "manifest_status": summary["manifest_status"]}))
if summary["bundle_status"] != "PASS":
  raise SystemExit(1)
PY
