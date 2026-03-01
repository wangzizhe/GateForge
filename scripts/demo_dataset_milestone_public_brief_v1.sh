#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_milestone_public_brief_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/checkpoint.json" <<'JSON'
{"status":"PASS","milestone_decision":"GO","checkpoint_score":85.0,"blockers":[],"model_asset_momentum_status":"PASS","model_asset_momentum_score":82.0,"delta_total_real_models":2,"delta_large_models":1}
JSON
cat > "$OUT_DIR/scoreboard.json" <<'JSON'
{"moat_public_score":86.0}
JSON
cat > "$OUT_DIR/alignment.json" <<'JSON'
{"alignment_score":88.0}
JSON
cat > "$OUT_DIR/proofbook.json" <<'JSON'
{"status":"PASS","target_gap_pressure_index":76.5,"model_asset_target_gap_score":24.0,"target_gap_band":"LOW"}
JSON
cat > "$OUT_DIR/supply_plan.json" <<'JSON'
{"status":"NEEDS_REVIEW","target_gap_supply_pressure_index":61}
JSON

python3 -m gateforge.dataset_milestone_public_brief_v1 \
  --milestone-checkpoint-summary "$OUT_DIR/checkpoint.json" \
  --moat-public-scoreboard-summary "$OUT_DIR/scoreboard.json" \
  --snapshot-moat-alignment-summary "$OUT_DIR/alignment.json" \
  --governance-decision-proofbook-summary "$OUT_DIR/proofbook.json" \
  --failure-supply-plan-summary "$OUT_DIR/supply_plan.json" \
  --out "$OUT_DIR/brief.json" \
  --report-out "$OUT_DIR/brief.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_milestone_public_brief_v1_demo")
brief = json.loads((out / "brief.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if isinstance(brief.get("milestone_status"), str) else "FAIL",
    "headline_present": "PASS" if isinstance(brief.get("headline"), str) and brief.get("headline") else "FAIL",
    "model_asset_momentum_present": "PASS" if isinstance(brief.get("model_asset_momentum_status"), str) else "FAIL",
    "target_gap_signal_present": "PASS" if isinstance(brief.get("target_gap_pressure_index"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "brief_status": brief.get("milestone_status"),
    "model_asset_momentum_status": brief.get("model_asset_momentum_status"),
    "model_asset_momentum_score": brief.get("model_asset_momentum_score"),
    "target_gap_pressure_index": brief.get("target_gap_pressure_index"),
    "model_asset_target_gap_score": brief.get("model_asset_target_gap_score"),
    "target_gap_narrative_status": brief.get("target_gap_narrative_status"),
    "bundle_status": bundle_status,
    "result_flags": flags
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "brief_status": brief.get("milestone_status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
