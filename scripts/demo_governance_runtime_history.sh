#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/governance_runtime_history_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

bash scripts/demo_runtime_decision_ledger_history.sh >/dev/null

cat > "$OUT_DIR/repair.json" <<'JSON'
{
  "profile_compare": {
    "downgrade_count": 0,
    "strict_downgrade_rate": 0.0
  }
}
JSON

cat > "$OUT_DIR/review.json" <<'JSON'
{
  "kpis": {
    "review_recovery_rate": 0.9,
    "strict_non_pass_rate": 0.1,
    "approval_rate": 0.8,
    "fail_rate": 0.1
  }
}
JSON

cat > "$OUT_DIR/matrix.json" <<'JSON'
{
  "matrix_status": "PASS"
}
JSON

python3 -m gateforge.governance_report \
  --repair-batch-summary "$OUT_DIR/repair.json" \
  --review-ledger-summary "$OUT_DIR/review.json" \
  --ci-matrix-summary "$OUT_DIR/matrix.json" \
  --runtime-ledger-summary artifacts/runtime_decision_ledger_demo/ledger_summary.json \
  --runtime-ledger-history-summary artifacts/runtime_decision_ledger_history_demo/history_summary.json \
  --runtime-ledger-history-trend artifacts/runtime_decision_ledger_history_demo/history_trend.json \
  --out "$OUT_DIR/governance_summary.json" \
  --report "$OUT_DIR/governance_summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/governance_runtime_history_demo")
summary = json.loads((out / "governance_summary.json").read_text(encoding="utf-8"))
risks = set(summary.get("risks", []))

flags = {
    "runtime_history_signal_present": "PASS"
    if summary.get("kpis", {}).get("runtime_ledger_history_trend_status") in {"PASS", "NEEDS_REVIEW"}
    else "FAIL",
    "runtime_history_source_present": "PASS"
    if summary.get("sources", {}).get("runtime_ledger_history_summary_path")
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "status": summary.get("status"),
    "runtime_history_trend_status": summary.get("kpis", {}).get("runtime_ledger_history_trend_status"),
    "runtime_history_related_risks": sorted([r for r in risks if r.startswith("runtime_ledger_history_")]),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
risks_lines = [f"- `{r}`" for r in payload["runtime_history_related_risks"]]
if not risks_lines:
    risks_lines = ["- `none`"]
flag_lines = [f"- {k}: `{v}`" for k, v in sorted(flags.items())]
(out / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Governance Runtime History Demo",
            "",
            f"- status: `{payload['status']}`",
            f"- runtime_history_trend_status: `{payload['runtime_history_trend_status']}`",
            f"- bundle_status: `{payload['bundle_status']}`",
            "",
            "## Runtime History Related Risks",
            "",
            *risks_lines,
            "",
            "## Result Flags",
            "",
            *flag_lines,
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "status": payload["status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
