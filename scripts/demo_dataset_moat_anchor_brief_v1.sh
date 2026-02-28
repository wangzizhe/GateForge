#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_anchor_brief_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/moat.json" <<'JSON'
{"status":"PASS","metrics":{"moat_score":84.0,"execution_readiness_index":82.0}}
JSON
cat > "$OUT_DIR/portfolio.json" <<'JSON'
{"status":"PASS","portfolio_strength_score":83.0,"total_real_models":5,"large_models":2}
JSON
cat > "$OUT_DIR/coverage.json" <<'JSON'
{"status":"PASS","coverage_depth_score":89.0,"high_risk_gaps_count":0}
JSON
cat > "$OUT_DIR/stability.json" <<'JSON'
{"status":"PASS","stability_score":81.0,"rare_failure_replay_rate":1.0}
JSON
cat > "$OUT_DIR/governance.json" <<'JSON'
{"status":"PASS"}
JSON

python3 -m gateforge.dataset_moat_anchor_brief_v1 \
  --moat-trend-snapshot-summary "$OUT_DIR/moat.json" \
  --real-model-intake-portfolio-summary "$OUT_DIR/portfolio.json" \
  --mutation-coverage-depth-summary "$OUT_DIR/coverage.json" \
  --failure-distribution-stability-summary "$OUT_DIR/stability.json" \
  --governance-snapshot-summary "$OUT_DIR/governance.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_moat_anchor_brief_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("anchor_brief_score"), (int, float)) else "FAIL",
    "recommendation_present": "PASS" if isinstance(summary.get("recommendation"), str) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "anchor_brief_status": summary.get("status"),
    "anchor_brief_score": summary.get("anchor_brief_score"),
    "recommendation": summary.get("recommendation"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "anchor_brief_status": demo["anchor_brief_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
