#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_hard_evidence_plan_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/representativeness_summary.json" <<'JSON'
{"status":"NEEDS_REVIEW","representativeness_score":66.0}
JSON

cat > "$OUT_DIR/depth_pressure_summary.json" <<'JSON'
{"status":"NEEDS_REVIEW","mutation_depth_pressure_index":49.0}
JSON

cat > "$OUT_DIR/stability_trend_summary.json" <<'JSON'
{"status":"NEEDS_REVIEW","trend":{"delta_avg_stability_score":-2.0,"delta_avg_distribution_drift_score":0.05}}
JSON

cat > "$OUT_DIR/moat_weekly_summary.json" <<'JSON'
{"status":"NEEDS_REVIEW"}
JSON

python3 -m gateforge.dataset_moat_hard_evidence_plan_v1 \
  --modelica-representativeness-gate-summary "$OUT_DIR/representativeness_summary.json" \
  --mutation-depth-pressure-board-summary "$OUT_DIR/depth_pressure_summary.json" \
  --failure-distribution-stability-history-trend-summary "$OUT_DIR/stability_trend_summary.json" \
  --moat-weekly-summary "$OUT_DIR/moat_weekly_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_moat_hard_evidence_plan_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "actions_present": "PASS" if isinstance(summary.get("planned_actions"), list) and len(summary.get("planned_actions")) > 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "plan_status": summary.get("status"),
    "priority_band": summary.get("priority_band"),
    "planned_actions_count": summary.get("planned_actions_count"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "plan_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
