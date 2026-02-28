#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_distribution_stability_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/previous_benchmark_summary.json" <<'JSON'
{
  "distribution_drift_score": 0.12,
  "regression_rate_after": 0.08,
  "distribution": {
    "failure_type_after": {
      "simulate_error": 4,
      "solver_non_convergence": 1,
      "semantic_regression": 1
    }
  }
}
JSON

cat > "$OUT_DIR/current_benchmark_summary.json" <<'JSON'
{
  "distribution_drift_score": 0.17,
  "regression_rate_after": 0.1,
  "distribution": {
    "failure_type_after": {
      "simulate_error": 5,
      "solver_non_convergence": 1,
      "semantic_regression": 1
    }
  }
}
JSON

python3 -m gateforge.dataset_failure_distribution_stability_v1 \
  --current-benchmark-summary "$OUT_DIR/current_benchmark_summary.json" \
  --previous-benchmark-summary "$OUT_DIR/previous_benchmark_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_failure_distribution_stability_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "stability_score_present": "PASS" if isinstance(summary.get("stability_score"), (int, float)) else "FAIL",
    "rare_rate_present": "PASS" if isinstance(summary.get("rare_failure_replay_rate"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "stability_status": summary.get("status"),
    "stability_score": summary.get("stability_score"),
    "drift_band": summary.get("drift_band"),
    "rare_failure_replay_rate": summary.get("rare_failure_replay_rate"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "stability_status": payload["stability_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
