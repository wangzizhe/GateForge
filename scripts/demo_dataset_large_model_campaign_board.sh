#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
OUT_DIR="artifacts/dataset_large_model_campaign_board_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/large_model_failure_queue.json" <<'JSON'
{"total_queue_items": 5, "status": "NEEDS_REVIEW"}
JSON
cat > "$OUT_DIR/pack_execution_tracker.json" <<'JSON'
{"status": "NEEDS_REVIEW", "large_scale_progress_percent": 35.0}
JSON
cat > "$OUT_DIR/moat_execution_forecast.json" <<'JSON'
{"status": "PASS", "projected_moat_score_30d": 68.2}
JSON

python3 -m gateforge.dataset_large_model_campaign_board \
  --large-model-failure-queue "$OUT_DIR/large_model_failure_queue.json" \
  --pack-execution-tracker "$OUT_DIR/pack_execution_tracker.json" \
  --moat-execution-forecast "$OUT_DIR/moat_execution_forecast.json" \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_large_model_campaign_board_demo")
p = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {"status_present": "PASS" if p.get("status") in {"PASS","NEEDS_REVIEW","FAIL"} else "FAIL", "phase_present": "PASS" if p.get("campaign_phase") in {"stabilize","scale_out","accelerate"} else "FAIL"}
summary = {"board_status": p.get("status"), "campaign_phase": p.get("campaign_phase"), "result_flags": flags, "bundle_status": "PASS" if all(v=="PASS" for v in flags.values()) else "FAIL"}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": summary["bundle_status"], "board_status": summary["board_status"]}))
if summary["bundle_status"] != "PASS":
  raise SystemExit(1)
PY
