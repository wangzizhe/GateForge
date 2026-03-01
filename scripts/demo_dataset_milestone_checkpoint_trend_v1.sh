#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_milestone_checkpoint_trend_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/current.json" <<'JSON'
{"status":"NEEDS_REVIEW","checkpoint_score":78.0,"milestone_decision":"LIMITED_GO","model_asset_momentum_status":"NEEDS_REVIEW","model_asset_momentum_score":74.0}
JSON
cat > "$OUT_DIR/previous.json" <<'JSON'
{"status":"PASS","checkpoint_score":84.0,"milestone_decision":"GO","model_asset_momentum_status":"PASS","model_asset_momentum_score":82.0}
JSON

python3 -m gateforge.dataset_milestone_checkpoint_trend_v1 \
  --summary "$OUT_DIR/current.json" \
  --previous-summary "$OUT_DIR/previous.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_milestone_checkpoint_trend_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
trend = summary.get("trend") or {}
flags = {
    "transition_present": "PASS" if "->" in str(trend.get("status_transition")) else "FAIL",
    "delta_present": "PASS" if isinstance(trend.get("checkpoint_score_delta"), (int, float)) else "FAIL",
    "momentum_transition_present": "PASS" if "->" in str(trend.get("model_asset_momentum_status_transition")) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "trend_status": summary.get("status"),
    "status_transition": trend.get("status_transition"),
    "model_asset_momentum_status_transition": trend.get("model_asset_momentum_status_transition"),
    "model_asset_momentum_score_delta": trend.get("model_asset_momentum_score_delta"),
    "bundle_status": bundle_status,
    "result_flags": flags
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "trend_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
