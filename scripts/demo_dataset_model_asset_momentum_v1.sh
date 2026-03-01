#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_model_asset_momentum_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/current_portfolio.json" <<'JSON'
{"status":"PASS","total_real_models":6,"large_models":2}
JSON
cat > "$OUT_DIR/previous_portfolio.json" <<'JSON'
{"status":"PASS","total_real_models":4,"large_models":1}
JSON

cat > "$OUT_DIR/current_coverage.json" <<'JSON'
{"status":"PASS","coverage_depth_score":92.0}
JSON
cat > "$OUT_DIR/previous_coverage.json" <<'JSON'
{"status":"PASS","coverage_depth_score":85.0}
JSON

cat > "$OUT_DIR/current_stability.json" <<'JSON'
{"status":"PASS","stability_score":84.0,"rare_failure_replay_rate":1.0}
JSON
cat > "$OUT_DIR/previous_stability.json" <<'JSON'
{"status":"PASS","stability_score":80.0,"rare_failure_replay_rate":0.85}
JSON

python3 -m gateforge.dataset_model_asset_momentum_v1 \
  --current-intake-portfolio "$OUT_DIR/current_portfolio.json" \
  --previous-intake-portfolio "$OUT_DIR/previous_portfolio.json" \
  --current-mutation-coverage-depth "$OUT_DIR/current_coverage.json" \
  --previous-mutation-coverage-depth "$OUT_DIR/previous_coverage.json" \
  --current-failure-distribution-stability "$OUT_DIR/current_stability.json" \
  --previous-failure-distribution-stability "$OUT_DIR/previous_stability.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_model_asset_momentum_v1_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "momentum_score_present": "PASS" if isinstance(payload.get("momentum_score"), (int, float)) else "FAIL",
    "delta_total_present": "PASS" if isinstance(payload.get("delta_total_real_models"), int) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "momentum_status": payload.get("status"),
    "momentum_score": payload.get("momentum_score"),
    "delta_total_real_models": payload.get("delta_total_real_models"),
    "delta_large_models": payload.get("delta_large_models"),
    "delta_mutation_coverage_depth_score": payload.get("delta_mutation_coverage_depth_score"),
    "delta_stability_score": payload.get("delta_stability_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "momentum_status": demo["momentum_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
