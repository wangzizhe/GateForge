#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_governance_history_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

bash scripts/demo_dataset_policy_lifecycle.sh >/dev/null

cat > "$OUT_DIR/previous_summary.json" <<'JSON'
{
  "total_records": 2,
  "status_counts": {"PASS": 2, "NEEDS_REVIEW": 0, "FAIL": 0},
  "applied_count": 2,
  "reject_count": 0
}
JSON

python3 -m gateforge.dataset_governance_history_trend \
  --summary artifacts/dataset_policy_lifecycle_demo/ledger_summary.json \
  --previous-summary "$OUT_DIR/previous_summary.json" \
  --out "$OUT_DIR/trend.json" \
  --report-out "$OUT_DIR/trend.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_governance_history_demo")
trend = json.loads((out / "trend.json").read_text(encoding="utf-8"))
flags = {
    "trend_status_present": "PASS" if trend.get("status") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
    "trend_alerts_present_field": "PASS" if isinstance((trend.get("trend") or {}).get("alerts"), list) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "status": trend.get("status"),
    "alerts_count": len((trend.get("trend") or {}).get("alerts") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Dataset Governance History Demo",
            "",
            f"- status: `{summary['status']}`",
            f"- alerts_count: `{summary['alerts_count']}`",
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
print(json.dumps({"bundle_status": bundle_status, "status": summary["status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"

