#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
OUT_DIR="artifacts/dataset_failure_supply_plan_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/large_model_failure_queue.json" <<'JSON'
{"total_queue_items": 6, "status": "NEEDS_REVIEW"}
JSON
cat > "$OUT_DIR/modelica_failure_pack_planner.json" <<'JSON'
{"large_target_new_cases": 4, "medium_target_new_cases": 5, "status": "NEEDS_REVIEW"}
JSON
cat > "$OUT_DIR/large_model_campaign_board.json" <<'JSON'
{"campaign_phase": "accelerate", "status": "NEEDS_REVIEW", "target_gap_pressure_index": 58.0, "model_asset_target_gap_score": 37.0}
JSON

python3 -m gateforge.dataset_failure_supply_plan \
  --large-model-failure-queue "$OUT_DIR/large_model_failure_queue.json" \
  --modelica-failure-pack-planner "$OUT_DIR/modelica_failure_pack_planner.json" \
  --large-model-campaign-board "$OUT_DIR/large_model_campaign_board.json" \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_failure_supply_plan_demo")
p = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if p.get("status") in {"PASS","NEEDS_REVIEW","FAIL"} else "FAIL",
    "weekly_target_present": "PASS" if isinstance(p.get("weekly_supply_target"), int) else "FAIL",
    "target_gap_supply_pressure_present": "PASS" if isinstance(p.get("target_gap_supply_pressure_index"), int) else "FAIL",
}
summary = {
    "supply_status": p.get("status"),
    "weekly_supply_target": p.get("weekly_supply_target"),
    "target_gap_supply_pressure_index": p.get("target_gap_supply_pressure_index"),
    "target_gap_pressure_index": p.get("target_gap_pressure_index"),
    "model_asset_target_gap_score": p.get("model_asset_target_gap_score"),
    "result_flags": flags,
    "bundle_status": "PASS" if all(v=="PASS" for v in flags.values()) else "FAIL"
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": summary["bundle_status"], "supply_status": summary["supply_status"]}))
if summary["bundle_status"] != "PASS":
  raise SystemExit(1)
PY
