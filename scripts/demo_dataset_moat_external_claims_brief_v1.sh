#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_external_claims_brief_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/report.json" <<'JSON'
{"status":"PASS","moat_defensibility_score":82.0}
JSON

cat > "$OUT_DIR/history.json" <<'JSON'
{"status":"PASS","publish_ready_streak":2,"avg_defensibility_score":80.0}
JSON

cat > "$OUT_DIR/trend.json" <<'JSON'
{"status":"PASS","trend":{"delta_avg_defensibility_score":1.5}}
JSON

cat > "$OUT_DIR/onepager.json" <<'JSON'
{"public_metrics":{"real_model_count":5,"reproducible_mutation_count":22,"failure_distribution_stability_score":83.5}}
JSON

python3 -m gateforge.dataset_moat_external_claims_brief_v1 \
  --moat-defensibility-report-summary "$OUT_DIR/report.json" \
  --moat-defensibility-history-summary "$OUT_DIR/history.json" \
  --moat-defensibility-history-trend-summary "$OUT_DIR/trend.json" \
  --moat-evidence-onepager-summary "$OUT_DIR/onepager.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_moat_external_claims_brief_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "claims_present": "PASS" if int(summary.get("claim_count", 0)) >= 3 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "claims_status": summary.get("status"),
    "publishable": summary.get("publishable"),
    "claim_confidence_score": summary.get("claim_confidence_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "claims_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
