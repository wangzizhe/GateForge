#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_milestone_evidence_page_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/moat_trend_snapshot_summary.json" <<'JSON'
{"status":"PASS","metrics":{"moat_score":82.0}}
JSON

cat > "$OUT_DIR/milestone_checkpoint_summary.json" <<'JSON'
{"status":"PASS","checkpoint_score":84.0,"milestone_decision":"GO"}
JSON

cat > "$OUT_DIR/milestone_checkpoint_trend_summary.json" <<'JSON'
{"status":"PASS","trend":{"status_transition":"PASS->PASS"}}
JSON

cat > "$OUT_DIR/milestone_public_brief_summary.json" <<'JSON'
{"milestone_status":"PASS","milestone_decision":"GO"}
JSON

cat > "$OUT_DIR/snapshot_moat_alignment_summary.json" <<'JSON'
{"alignment_score":81.0}
JSON

python3 -m gateforge.dataset_moat_milestone_evidence_page_v1 \
  --moat-trend-snapshot-summary "$OUT_DIR/moat_trend_snapshot_summary.json" \
  --milestone-checkpoint-summary "$OUT_DIR/milestone_checkpoint_summary.json" \
  --milestone-checkpoint-trend-summary "$OUT_DIR/milestone_checkpoint_trend_summary.json" \
  --milestone-public-brief-summary "$OUT_DIR/milestone_public_brief_summary.json" \
  --snapshot-moat-alignment-summary "$OUT_DIR/snapshot_moat_alignment_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_moat_milestone_evidence_page_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
claims = summary.get("public_claims") if isinstance(summary.get("public_claims"), list) else []
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("evidence_page_score"), (int, float)) else "FAIL",
    "claims_present": "PASS" if len(claims) >= 3 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "evidence_page_status": summary.get("status"),
    "publishable": summary.get("publishable"),
    "evidence_page_score": summary.get("evidence_page_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "evidence_page_status": payload["evidence_page_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
