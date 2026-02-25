#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_policy_autotune_history_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

bash scripts/demo_dataset_strategy_autotune.sh >/dev/null

python3 -m gateforge.dataset_policy_autotune_history \
  --record artifacts/dataset_strategy_autotune_demo/advisor.json \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/history_summary.json" \
  --report-out "$OUT_DIR/history_summary.md"

cat > "$OUT_DIR/history_summary_previous.json" <<'JSON'
{
  "strict_suggestion_rate": 0.0,
  "avg_confidence": 0.7
}
JSON

python3 -m gateforge.dataset_policy_autotune_history_trend \
  --current "$OUT_DIR/history_summary.json" \
  --previous "$OUT_DIR/history_summary_previous.json" \
  --out "$OUT_DIR/history_trend.json" \
  --report-out "$OUT_DIR/history_trend.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_policy_autotune_history_demo")
history = json.loads((out / "history_summary.json").read_text(encoding="utf-8"))
trend = json.loads((out / "history_trend.json").read_text(encoding="utf-8"))
flags = {
    "history_total_records_ok": "PASS" if int(history.get("total_records", 0) or 0) >= 1 else "FAIL",
    "trend_status_present": "PASS" if trend.get("status") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "history_total_records": history.get("total_records"),
    "history_latest_profile": history.get("latest_suggested_profile"),
    "trend_status": trend.get("status"),
    "trend_alert_count": len((trend.get("trend") or {}).get("alerts") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Dataset Policy Auto-Tune History Demo",
            "",
            f"- history_total_records: `{summary['history_total_records']}`",
            f"- history_latest_profile: `{summary['history_latest_profile']}`",
            f"- trend_status: `{summary['trend_status']}`",
            f"- trend_alert_count: `{summary['trend_alert_count']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "trend_status": summary["trend_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"

