#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/policy_autotune_governance_advisor_history_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

bash scripts/demo_policy_autotune_governance_advisor.sh >/dev/null

cat > "$OUT_DIR/advisor_previous.json" <<'JSON'
{
  "advice": {
    "action": "KEEP",
    "suggested_policy_profile": "default",
    "confidence": 0.65,
    "reasons": ["stable"],
    "threshold_patch": {
      "require_min_top_score_margin": null,
      "require_min_pairwise_net_margin": null,
      "require_min_explanation_quality": null
    },
    "dry_run": true
  }
}
JSON

python3 -m gateforge.policy_autotune_governance_advisor_history \
  --record "$OUT_DIR/advisor_previous.json" \
  --record artifacts/policy_autotune_governance_advisor_demo/advisor.json \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

cat > "$OUT_DIR/summary_previous.json" <<'JSON'
{
  "tighten_rate": 0.0,
  "rollback_review_rate": 0.0
}
JSON

python3 -m gateforge.policy_autotune_governance_advisor_history_trend \
  --current "$OUT_DIR/summary.json" \
  --previous "$OUT_DIR/summary_previous.json" \
  --out "$OUT_DIR/trend.json" \
  --report-out "$OUT_DIR/trend.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/policy_autotune_governance_advisor_history_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
trend = json.loads((out / "trend.json").read_text(encoding="utf-8"))

flags = {
    "history_total_records_ok": "PASS" if int(summary.get("total_records", 0)) >= 2 else "FAIL",
    "history_latest_action_present": "PASS" if summary.get("latest_action") in {"KEEP", "TIGHTEN", "ROLLBACK_REVIEW"} else "FAIL",
    "trend_status_present": "PASS" if trend.get("status") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
result = {
    "latest_action": summary.get("latest_action"),
    "tighten_rate": summary.get("tighten_rate"),
    "rollback_review_rate": summary.get("rollback_review_rate"),
    "pairwise_patch_rate": summary.get("pairwise_patch_rate"),
    "trend_status": trend.get("status"),
    "trend_alerts": (trend.get("trend") or {}).get("alerts", []),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Policy Auto-Tune Governance Advisor History Demo",
            "",
            f"- latest_action: `{result['latest_action']}`",
            f"- tighten_rate: `{result['tighten_rate']}`",
            f"- rollback_review_rate: `{result['rollback_review_rate']}`",
            f"- pairwise_patch_rate: `{result['pairwise_patch_rate']}`",
            f"- trend_status: `{result['trend_status']}`",
            f"- bundle_status: `{result['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "trend_status": result["trend_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
