#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/runtime_decision_ledger_history_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

bash scripts/demo_runtime_decision_ledger.sh >/dev/null

cp artifacts/runtime_decision_ledger_demo/ledger_summary.json "$OUT_DIR/current_summary.json"

cat > "$OUT_DIR/previous_summary.json" <<'JSON'
{
  "generated_at_utc": "2026-01-01T00:00:00+00:00",
  "total_records": 8,
  "status_counts": {
    "PASS": 7,
    "FAIL": 1
  },
  "source_counts": {
    "run": 4,
    "autopilot": 4
  },
  "kpis": {
    "pass_rate": 0.875,
    "fail_rate": 0.125,
    "needs_review_rate": 0.0
  }
}
JSON

python3 -m gateforge.runtime_ledger_history \
  --record "$OUT_DIR/previous_summary.json" \
  --record "$OUT_DIR/current_summary.json" \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/history_summary.json" \
  --report-out "$OUT_DIR/history_summary.md"

cat > "$OUT_DIR/previous_for_trend.json" <<'JSON'
{
  "total_records": 1,
  "avg_pass_rate": 0.95,
  "avg_fail_rate": 0.05,
  "avg_needs_review_rate": 0.0
}
JSON

python3 -m gateforge.runtime_ledger_history_trend \
  --current "$OUT_DIR/history_summary.json" \
  --previous "$OUT_DIR/previous_for_trend.json" \
  --out "$OUT_DIR/history_trend.json" \
  --report-out "$OUT_DIR/history_trend.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/runtime_decision_ledger_history_demo")
history = json.loads((out / "history_summary.json").read_text(encoding="utf-8"))
trend = json.loads((out / "history_trend.json").read_text(encoding="utf-8"))

flags = {
    "history_records_at_least_two": "PASS" if int(history.get("total_records", 0)) >= 2 else "FAIL",
    "history_has_source_counts": "PASS" if isinstance(history.get("source_counts"), dict) else "FAIL",
    "trend_status_present": "PASS" if trend.get("status") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "history_total_records": history.get("total_records"),
    "history_alerts": history.get("alerts", []),
    "trend_status": trend.get("status"),
    "trend_alerts": (trend.get("trend") or {}).get("alerts", []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Runtime Decision Ledger History Demo",
            "",
            f"- history_total_records: `{payload['history_total_records']}`",
            f"- trend_status: `{payload['trend_status']}`",
            f"- bundle_status: `{payload['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "trend_status": payload["trend_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
