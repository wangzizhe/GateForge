#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_snapshot_moat_alignment_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/governance_snapshot_summary.json" <<'JSON'
{"status":"PASS","risks":[]}
JSON

cat > "$OUT_DIR/governance_snapshot_trend_summary.json" <<'JSON'
{"status":"PASS","trend":{"severity_score":2}}
JSON

cat > "$OUT_DIR/moat_public_scoreboard_summary.json" <<'JSON'
{"status":"PASS","moat_public_score":84.0}
JSON

cat > "$OUT_DIR/mutation_campaign_tracker_summary.json" <<'JSON'
{"status":"PASS","completion_ratio_pct":88.0}
JSON

cat > "$OUT_DIR/modelica_library_provenance_guard_summary.json" <<'JSON'
{"status":"PASS","unknown_license_ratio_pct":1.0}
JSON

python3 -m gateforge.dataset_snapshot_moat_alignment_v1 \
  --governance-snapshot-summary "$OUT_DIR/governance_snapshot_summary.json" \
  --governance-snapshot-trend-summary "$OUT_DIR/governance_snapshot_trend_summary.json" \
  --moat-public-scoreboard-summary "$OUT_DIR/moat_public_scoreboard_summary.json" \
  --mutation-campaign-tracker-summary "$OUT_DIR/mutation_campaign_tracker_summary.json" \
  --modelica-library-provenance-guard-summary "$OUT_DIR/modelica_library_provenance_guard_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_snapshot_moat_alignment_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if summary.get("alignment_score") is not None else "FAIL",
    "contradiction_count_present": "PASS" if summary.get("contradiction_count") is not None else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "alignment_status": summary.get("status"),
    "alignment_score": summary.get("alignment_score"),
    "contradiction_count": summary.get("contradiction_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "alignment_status": payload["alignment_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
