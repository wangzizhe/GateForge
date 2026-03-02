#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_execution_cadence_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/plan.json" <<'JSON'
{"status":"PASS","execution_focus_score":76.0}
JSON

cat > "$OUT_DIR/depth.json" <<'JSON'
{"status":"NEEDS_REVIEW","mutation_depth_pressure_index":31.0,"recommended_weekly_mutation_target":11}
JSON

cat > "$OUT_DIR/supply.json" <<'JSON'
{"status":"PASS","growth_velocity_score":82.0,"supply_pipeline_score":79.0}
JSON

cat > "$OUT_DIR/campaign.json" <<'JSON'
{"status":"PASS","completion_ratio_pct":74.0}
JSON

python3 -m gateforge.dataset_moat_execution_cadence_v1 \
  --moat-hard-evidence-plan-summary "$OUT_DIR/plan.json" \
  --mutation-depth-pressure-board-summary "$OUT_DIR/depth.json" \
  --real-model-supply-pipeline-summary "$OUT_DIR/supply.json" \
  --mutation-campaign-tracker-summary "$OUT_DIR/campaign.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_moat_execution_cadence_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("execution_cadence_score"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "cadence_status": summary.get("status"),
    "execution_cadence_score": summary.get("execution_cadence_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "cadence_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
