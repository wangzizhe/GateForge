#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/runtime_decision_ledger_trend_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/previous.json" <<'JSON'
{
  "total_records": 20,
  "kpis": {
    "pass_rate": 0.8,
    "fail_rate": 0.1,
    "needs_review_rate": 0.1
  }
}
JSON

cat > "$OUT_DIR/current.json" <<'JSON'
{
  "total_records": 28,
  "kpis": {
    "pass_rate": 0.6,
    "fail_rate": 0.25,
    "needs_review_rate": 0.15
  }
}
JSON

set +e
python3 -m gateforge.runtime_ledger_trend \
  --current "$OUT_DIR/current.json" \
  --previous "$OUT_DIR/previous.json" \
  --out "$OUT_DIR/trend.json" \
  --report "$OUT_DIR/trend.md"
TREND_RC=$?
set -e

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/runtime_decision_ledger_trend_demo")
trend = json.loads((out / "trend.json").read_text(encoding="utf-8"))
flags = {
    "status_expected_needs_review": "PASS" if trend.get("status") == "NEEDS_REVIEW" else "FAIL",
    "alert_expected_fail_rate_regression": "PASS"
    if "fail_rate_regression_detected" in (trend.get("alerts") or [])
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "trend_status": trend.get("status"),
    "alerts": trend.get("alerts", []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Runtime Decision Ledger Trend Demo",
            "",
            f"- trend_status: `{summary['trend_status']}`",
            f"- alerts: `{summary['alerts']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- status_expected_needs_review: `{flags['status_expected_needs_review']}`",
            f"- alert_expected_fail_rate_regression: `{flags['alert_expected_fail_rate_regression']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

if [[ "$TREND_RC" -ne 1 ]]; then
  echo "expected trend command to exit 1, got $TREND_RC" >&2
  exit 1
fi

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
