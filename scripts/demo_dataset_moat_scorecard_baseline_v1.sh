#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_scorecard_baseline_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/real_model_intake_portfolio_summary.json" <<'JSON'
{"bundle_status":"PASS","portfolio_status":"PASS","total_real_models":4,"large_models":1}
JSON
cat > "$OUT_DIR/mutation_execution_matrix_summary.json" <<'JSON'
{"matrix_status":"PASS","matrix_cell_count":12,"matrix_execution_ratio_pct":100.0}
JSON
cat > "$OUT_DIR/failure_distribution_benchmark_summary.json" <<'JSON'
{"benchmark_v2_status":"PASS","failure_type_drift":0.08,"model_scale_drift":0.12}
JSON
cat > "$OUT_DIR/gateforge_vs_plain_ci_benchmark_summary.json" <<'JSON'
{"comparison_status":"PASS","verdict":"GATEFORGE_ADVANTAGE","advantage_score":10}
JSON
cat > "$OUT_DIR/moat_trend_snapshot_summary.json" <<'JSON'
{"moat_score":74.2}
JSON

python3 -m gateforge.dataset_moat_scorecard_baseline_v1 \
  --real-model-intake-portfolio-summary "$OUT_DIR/real_model_intake_portfolio_summary.json" \
  --mutation-execution-matrix-summary "$OUT_DIR/mutation_execution_matrix_summary.json" \
  --failure-distribution-benchmark-summary "$OUT_DIR/failure_distribution_benchmark_summary.json" \
  --gateforge-vs-plain-ci-benchmark-summary "$OUT_DIR/gateforge_vs_plain_ci_benchmark_summary.json" \
  --moat-trend-snapshot-summary "$OUT_DIR/moat_trend_snapshot_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_moat_scorecard_baseline_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
indicators = summary.get("indicators") if isinstance(summary.get("indicators"), dict) else {}
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "baseline_id_present": "PASS" if isinstance(summary.get("baseline_id"), str) and summary.get("baseline_id") else "FAIL",
    "indicators_present": "PASS" if isinstance(indicators.get("real_model_count"), int) and isinstance(indicators.get("reproducible_mutation_count"), int) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "scorecard_status": summary.get("status"),
    "baseline_id": summary.get("baseline_id"),
    "real_model_count": indicators.get("real_model_count"),
    "reproducible_mutation_count": indicators.get("reproducible_mutation_count"),
    "failure_distribution_stability_score": indicators.get("failure_distribution_stability_score"),
    "gateforge_vs_plain_ci_advantage_score": indicators.get("gateforge_vs_plain_ci_advantage_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "scorecard_status": payload["scorecard_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
