#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
OUT_DIR="artifacts/dataset_external_proof_score_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/evidence_release_manifest.json" <<'JSON'
{"release_ready": true, "artifacts": [{"name":"a"},{"name":"b"},{"name":"c"}]}
JSON
cat > "$OUT_DIR/moat_execution_forecast.json" <<'JSON'
{"projected_moat_score_30d": 72.4}
JSON
cat > "$OUT_DIR/moat_trend_snapshot_summary.json" <<'JSON'
{"metrics":{"execution_readiness_index":82.0}}
JSON
cat > "$OUT_DIR/governance_decision_proofbook.json" <<'JSON'
{"decision": "PROMOTE_WITH_GUARDS"}
JSON

python3 -m gateforge.dataset_external_proof_score \
  --evidence-release-manifest "$OUT_DIR/evidence_release_manifest.json" \
  --moat-execution-forecast "$OUT_DIR/moat_execution_forecast.json" \
  --moat-trend-snapshot-summary "$OUT_DIR/moat_trend_snapshot_summary.json" \
  --governance-decision-proofbook "$OUT_DIR/governance_decision_proofbook.json" \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_external_proof_score_demo")
p = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if p.get("status") in {"PASS","NEEDS_REVIEW","FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(p.get("proof_score"), (int,float)) else "FAIL",
    "execution_readiness_present": "PASS" if isinstance(p.get("execution_readiness_index"), (int,float)) else "FAIL",
}
summary = {
    "proof_status": p.get("status"),
    "proof_score": p.get("proof_score"),
    "execution_readiness_index": p.get("execution_readiness_index"),
    "result_flags": flags,
    "bundle_status": "PASS" if all(v=="PASS" for v in flags.values()) else "FAIL",
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": summary["bundle_status"], "proof_status": summary["proof_status"]}))
if summary["bundle_status"] != "PASS":
  raise SystemExit(1)
PY
