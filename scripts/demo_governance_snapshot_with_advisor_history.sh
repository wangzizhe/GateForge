#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/governance_snapshot_advisor_history_demo"
mkdir -p "$OUT_DIR"

bash scripts/demo_governance_snapshot.sh >/dev/null
bash scripts/demo_policy_autotune_governance_advisor_history.sh >/dev/null

python3 -m gateforge.governance_report \
  --repair-batch-summary artifacts/repair_batch_compare_demo/summary.json \
  --review-ledger-summary artifacts/review_kpi_demo/kpi_summary.json \
  --ci-matrix-summary artifacts/ci_matrix_summary.json \
  --invariant-repair-compare-summary artifacts/invariant_repair_profile_compare_demo/compare.json \
  --mutation-dashboard-summary artifacts/mutation_dashboard_demo/summary.json \
  --policy-autotune-advisor-history-summary artifacts/policy_autotune_governance_advisor_history_demo/demo_summary.json \
  --out "$OUT_DIR/summary.json" \
  --report "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/governance_snapshot_advisor_history_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
kpis = summary.get("kpis", {})

flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "advisor_kpi_present": "PASS" if "policy_autotune_advisor_trend_status" in kpis else "FAIL",
    "risks_list_present": "PASS" if isinstance(summary.get("risks", []), list) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "status": summary.get("status"),
    "advisor_trend_status": kpis.get("policy_autotune_advisor_trend_status"),
    "advisor_latest_action": kpis.get("policy_autotune_advisor_latest_action"),
    "advisor_tighten_rate": kpis.get("policy_autotune_advisor_tighten_rate"),
    "advisor_rollback_review_rate": kpis.get("policy_autotune_advisor_rollback_review_rate"),
    "risk_count": len(summary.get("risks", [])),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Governance Snapshot with Advisor History Demo",
            "",
            f"- status: `{payload['status']}`",
            f"- advisor_trend_status: `{payload['advisor_trend_status']}`",
            f"- advisor_latest_action: `{payload['advisor_latest_action']}`",
            f"- advisor_tighten_rate: `{payload['advisor_tighten_rate']}`",
            f"- advisor_rollback_review_rate: `{payload['advisor_rollback_review_rate']}`",
            f"- risk_count: `{payload['risk_count']}`",
            f"- bundle_status: `{bundle_status}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "status": payload["status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
