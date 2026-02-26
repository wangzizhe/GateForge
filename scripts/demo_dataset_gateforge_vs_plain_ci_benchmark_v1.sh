#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_gateforge_vs_plain_ci_benchmark_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/gateforge_summary.json" <<'JSON'
{
  "blocked_critical_count": 14,
  "escaped_critical_count": 1,
  "false_positive_rate": 0.07,
  "needs_review_count": 11
}
JSON

cat > "$OUT_DIR/plain_ci_summary.json" <<'JSON'
{
  "blocked_critical_count": 9,
  "escaped_critical_count": 4,
  "false_positive_rate": 0.09,
  "needs_review_count": 3
}
JSON

python3 -m gateforge.dataset_gateforge_vs_plain_ci_benchmark_v1 \
  --gateforge-summary "$OUT_DIR/gateforge_summary.json" \
  --plain-ci-summary "$OUT_DIR/plain_ci_summary.json" \
  --max-fp-regression 0.03 \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_gateforge_vs_plain_ci_benchmark_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "verdict_present": "PASS" if summary.get("verdict") in {"GATEFORGE_ADVANTAGE", "INCONCLUSIVE", "PLAIN_CI_BETTER"} else "FAIL",
    "delta_present": "PASS" if isinstance(summary.get("delta"), dict) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "comparison_status": summary.get("status"),
    "verdict": summary.get("verdict"),
    "advantage_score": summary.get("advantage_score"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "comparison_status": summary_out["comparison_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
