#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_milestone_checkpoint_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/moat_trend_snapshot.json" <<'JSON'
{"status":"PASS","metrics":{"moat_score":84.0}}
JSON
cat > "$OUT_DIR/moat_public_scoreboard.json" <<'JSON'
{"status":"PASS","moat_public_score":86.0}
JSON
cat > "$OUT_DIR/snapshot_moat_alignment.json" <<'JSON'
{"status":"PASS","alignment_score":88.0,"contradiction_count":0}
JSON
cat > "$OUT_DIR/release_candidate.json" <<'JSON'
{"status":"PASS","release_candidate_score":85.0,"candidate_decision":"GO"}
JSON
cat > "$OUT_DIR/model_asset_momentum.json" <<'JSON'
{"status":"PASS","momentum_score":82.0,"delta_total_real_models":2,"delta_large_models":1}
JSON

python3 -m gateforge.dataset_milestone_checkpoint_v1 \
  --moat-trend-snapshot-summary "$OUT_DIR/moat_trend_snapshot.json" \
  --moat-public-scoreboard-summary "$OUT_DIR/moat_public_scoreboard.json" \
  --snapshot-moat-alignment-summary "$OUT_DIR/snapshot_moat_alignment.json" \
  --modelica-release-candidate-gate-summary "$OUT_DIR/release_candidate.json" \
  --model-asset-momentum-summary "$OUT_DIR/model_asset_momentum.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_milestone_checkpoint_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "decision_present": "PASS" if summary.get("milestone_decision") in {"GO", "LIMITED_GO", "HOLD"} else "FAIL",
    "model_asset_momentum_present": "PASS" if summary.get("model_asset_momentum_status") in {"PASS", "NEEDS_REVIEW", "FAIL", "UNKNOWN"} else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "checkpoint_status": summary.get("status"),
    "milestone_decision": summary.get("milestone_decision"),
    "model_asset_momentum_status": summary.get("model_asset_momentum_status"),
    "model_asset_momentum_score": summary.get("model_asset_momentum_score"),
    "bundle_status": bundle_status,
    "result_flags": flags
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "checkpoint_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
