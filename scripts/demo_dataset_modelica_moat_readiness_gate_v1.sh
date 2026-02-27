#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_modelica_moat_readiness_gate_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/license_summary.json" <<'JSON'
{"status": "PASS"}
JSON

cat > "$OUT_DIR/recipe_summary.json" <<'JSON'
{"status": "PASS"}
JSON

cat > "$OUT_DIR/yield_summary.json" <<'JSON'
{"status": "PASS"}
JSON

cat > "$OUT_DIR/backlog_summary.json" <<'JSON'
{"status": "PASS", "p0_count": 0}
JSON

cat > "$OUT_DIR/intake_summary.json" <<'JSON'
{
  "status": "PASS",
  "accepted_count": 4,
  "accepted_large_count": 1,
  "reject_rate_pct": 20.0,
  "weekly_target_status": "PASS"
}
JSON

cat > "$OUT_DIR/external_proof_summary.json" <<'JSON'
{"external_proof_score": 82}
JSON

python3 -m gateforge.dataset_modelica_moat_readiness_gate_v1 \
  --real-model-license-compliance-summary "$OUT_DIR/license_summary.json" \
  --modelica-mutation-recipe-library-summary "$OUT_DIR/recipe_summary.json" \
  --real-model-failure-yield-summary "$OUT_DIR/yield_summary.json" \
  --real-model-intake-backlog-summary "$OUT_DIR/backlog_summary.json" \
  --real-model-intake-summary "$OUT_DIR/intake_summary.json" \
  --external-proof-score-summary "$OUT_DIR/external_proof_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_modelica_moat_readiness_gate_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if float(summary.get("moat_readiness_score", 0) or 0) >= 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "moat_gate_status": summary.get("status"),
    "confidence_level": summary.get("confidence_level"),
    "critical_blockers_count": len(summary.get("critical_blockers") or []),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "moat_gate_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
