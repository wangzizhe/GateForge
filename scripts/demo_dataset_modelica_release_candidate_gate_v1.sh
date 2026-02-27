#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_modelica_release_candidate_gate_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/supply_summary.json" <<'JSON'
{"status":"PASS","supply_health_score":84.0,"supply_gap_count":0}
JSON
cat > "$OUT_DIR/audit_summary.json" <<'JSON'
{"status":"PASS","execution_coverage_pct":82.0,"missing_recipe_count":1}
JSON
cat > "$OUT_DIR/moat_summary.json" <<'JSON'
{"status":"PASS","moat_readiness_score":85.0}
JSON

python3 -m gateforge.dataset_modelica_release_candidate_gate_v1 \
  --real-model-supply-health-summary "$OUT_DIR/supply_summary.json" \
  --mutation-recipe-execution-audit-summary "$OUT_DIR/audit_summary.json" \
  --modelica-moat-readiness-gate-summary "$OUT_DIR/moat_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_modelica_release_candidate_gate_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "decision_present": "PASS" if summary.get("candidate_decision") in {"GO", "LIMITED_GO", "HOLD"} else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({"release_candidate_status": summary.get("status"), "candidate_decision": summary.get("candidate_decision"), "release_candidate_score": summary.get("release_candidate_score"), "bundle_status": bundle_status, "result_flags": flags}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "release_candidate_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
