#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_public_scoreboard_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/anchor_public_release_v1_summary.json" <<'JSON'
{"status":"PASS","public_release_score":86.0}
JSON

cat > "$OUT_DIR/evidence_chain_summary.json" <<'JSON'
{"status":"PASS","chain_health_score":82.0}
JSON

cat > "$OUT_DIR/modelica_moat_roadmap_v1_summary.json" <<'JSON'
{"status":"NEEDS_REVIEW","roadmap_health_score":75.0}
JSON

cat > "$OUT_DIR/mutation_campaign_tracker_v1_summary.json" <<'JSON'
{"status":"PASS","completion_ratio_pct":88.0}
JSON

cat > "$OUT_DIR/modelica_library_expansion_plan_v1_summary.json" <<'JSON'
{"status":"PASS","expansion_readiness_score":80.0}
JSON

cat > "$OUT_DIR/modelica_library_provenance_guard_v1_summary.json" <<'JSON'
{"status":"PASS","provenance_completeness_pct":98.0}
JSON

python3 -m gateforge.dataset_moat_public_scoreboard_v1 \
  --anchor-public-release-v1-summary "$OUT_DIR/anchor_public_release_v1_summary.json" \
  --evidence-chain-summary "$OUT_DIR/evidence_chain_summary.json" \
  --modelica-moat-roadmap-v1-summary "$OUT_DIR/modelica_moat_roadmap_v1_summary.json" \
  --mutation-campaign-tracker-v1-summary "$OUT_DIR/mutation_campaign_tracker_v1_summary.json" \
  --modelica-library-expansion-plan-v1-summary "$OUT_DIR/modelica_library_expansion_plan_v1_summary.json" \
  --modelica-library-provenance-guard-v1-summary "$OUT_DIR/modelica_library_provenance_guard_v1_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_moat_public_scoreboard_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if summary.get("moat_public_score") is not None else "FAIL",
    "verdict_present": "PASS" if summary.get("verdict") in {"STRONG_MOAT_SIGNAL", "EMERGING_MOAT", "INSUFFICIENT_EVIDENCE"} else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "scoreboard_status": summary.get("status"),
    "moat_public_score": summary.get("moat_public_score"),
    "verdict": summary.get("verdict"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "scoreboard_status": payload["scoreboard_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
