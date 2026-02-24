#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/governance_policy_patch_dashboard_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

bash scripts/demo_governance_policy_patch_history.sh >/dev/null

cat > "$OUT_DIR/previous_history_summary.json" <<'JSON'
{
  "total_records": 2,
  "latest_status": "FAIL",
  "status_counts": {
    "PASS": 0,
    "NEEDS_REVIEW": 1,
    "FAIL": 1
  },
  "applied_count": 0,
  "reject_count": 1,
  "pairwise_threshold_enabled_count": 0,
  "latest_pairwise_threshold": null
}
JSON

python3 -m gateforge.governance_policy_patch_history_trend \
  --summary artifacts/governance_policy_patch_history_demo/summary.json \
  --previous-summary "$OUT_DIR/previous_history_summary.json" \
  --out "$OUT_DIR/trend.json" \
  --report "$OUT_DIR/trend.md"

python3 -m gateforge.governance_policy_patch_rollback_advisor \
  --summary artifacts/governance_policy_patch_history_demo/summary.json \
  --trend "$OUT_DIR/trend.json" \
  --out "$OUT_DIR/rollback_advice.json" \
  --report "$OUT_DIR/rollback_advice.md"

python3 -m gateforge.governance_policy_patch_dashboard \
  --proposal artifacts/governance_policy_patch_apply_demo/proposal.json \
  --apply artifacts/governance_policy_patch_apply_demo/apply.approve_apply.json \
  --history artifacts/governance_policy_patch_history_demo/summary.json \
  --trend "$OUT_DIR/trend.json" \
  --rollback "$OUT_DIR/rollback_advice.json" \
  --out "$OUT_DIR/summary.json" \
  --report "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/governance_policy_patch_dashboard_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
rollback = json.loads((out / "rollback_advice.json").read_text(encoding="utf-8"))

flags = {
    "bundle_pass": "PASS" if summary.get("bundle_status") == "PASS" else "FAIL",
    "proposal_present": "PASS" if bool(summary.get("proposal_id")) else "FAIL",
    "history_records_present": "PASS" if int(summary.get("total_records", 0)) >= 1 else "FAIL",
    "rollback_decision_present": "PASS" if rollback.get("advice", {}).get("decision") in {"KEEP", "ROLLBACK_RECOMMENDED"} else "FAIL",
    "pairwise_signal_present": "PASS" if isinstance(summary.get("pairwise_threshold_enabled_count"), int) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

demo = {
    "bundle_status": bundle_status,
    "dashboard_status": summary.get("bundle_status"),
    "rollback_decision": summary.get("rollback_decision"),
    "rollback_recommended": summary.get("rollback_recommended"),
    "total_records": summary.get("total_records"),
    "pairwise_threshold_enabled_count": summary.get("pairwise_threshold_enabled_count"),
    "latest_pairwise_threshold": summary.get("latest_pairwise_threshold"),
    "pairwise_threshold_enable_rate_delta": summary.get("pairwise_threshold_enable_rate_delta"),
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Governance Policy Patch Dashboard Demo",
            "",
            f"- bundle_status: `{demo['bundle_status']}`",
            f"- dashboard_status: `{demo['dashboard_status']}`",
            f"- rollback_decision: `{demo['rollback_decision']}`",
            f"- rollback_recommended: `{demo['rollback_recommended']}`",
            f"- total_records: `{demo['total_records']}`",
            f"- pairwise_threshold_enabled_count: `{demo['pairwise_threshold_enabled_count']}`",
            f"- latest_pairwise_threshold: `{demo['latest_pairwise_threshold']}`",
            f"- pairwise_threshold_enable_rate_delta: `{demo['pairwise_threshold_enable_rate_delta']}`",
            "",
            "## Result Flags",
            "",
            f"- bundle_pass: `{flags['bundle_pass']}`",
            f"- proposal_present: `{flags['proposal_present']}`",
            f"- history_records_present: `{flags['history_records_present']}`",
            f"- rollback_decision_present: `{flags['rollback_decision_present']}`",
            f"- pairwise_signal_present: `{flags['pairwise_signal_present']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
