#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/policy_autotune_governance_history_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

bash scripts/demo_policy_autotune_governance.sh >/dev/null

cat > "$OUT_DIR/summary_previous.json" <<'JSON'
{
  "improvement_rate": 0.5,
  "regression_rate": 0.0
}
JSON

python3 -m gateforge.policy_autotune_governance_history \
  --record artifacts/policy_autotune_governance_demo/summary.json \
  --record artifacts/policy_autotune_governance_demo/summary.json \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 -m gateforge.policy_autotune_governance_history_trend \
  --current "$OUT_DIR/summary.json" \
  --previous "$OUT_DIR/summary_previous.json" \
  --out "$OUT_DIR/trend.json" \
  --report-out "$OUT_DIR/trend.md"

python3 -m gateforge.policy_autotune_governance_dashboard \
  --flow-summary artifacts/policy_autotune_governance_demo/flow_summary.json \
  --effectiveness artifacts/policy_autotune_governance_demo/effectiveness.json \
  --history "$OUT_DIR/summary.json" \
  --trend "$OUT_DIR/trend.json" \
  --out "$OUT_DIR/dashboard.json" \
  --report-out "$OUT_DIR/dashboard.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/policy_autotune_governance_history_demo")
dashboard = json.loads((out / "dashboard.json").read_text(encoding="utf-8"))

flags = {
    "dashboard_bundle_pass": "PASS" if dashboard.get("bundle_status") == "PASS" else "FAIL",
    "effectiveness_decision_present": "PASS" if dashboard.get("latest_effectiveness_decision") in {"IMPROVED", "UNCHANGED", "REGRESSED"} else "FAIL",
    "trend_status_present": "PASS" if dashboard.get("trend_status") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
    "tuned_compare_explanation_present": "PASS"
    if isinstance(dashboard.get("tuned_top_score_margin"), int)
    and isinstance(dashboard.get("tuned_explanation_completeness"), int)
    else "FAIL",
    "tuned_pairwise_signal_present": "PASS"
    if isinstance(dashboard.get("tuned_pairwise_net_margin"), int)
    else "FAIL",
    "tuned_leaderboard_signal_present": "PASS"
    if isinstance(dashboard.get("tuned_leader_profile"), str)
    and isinstance(dashboard.get("tuned_runner_up_score_gap_to_best"), int)
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
result = {
    "latest_effectiveness_decision": dashboard.get("latest_effectiveness_decision"),
    "improvement_rate": dashboard.get("improvement_rate"),
    "regression_rate": dashboard.get("regression_rate"),
    "trend_status": dashboard.get("trend_status"),
    "tuned_top_score_margin": dashboard.get("tuned_top_score_margin"),
    "tuned_explanation_completeness": dashboard.get("tuned_explanation_completeness"),
    "tuned_pairwise_net_margin": dashboard.get("tuned_pairwise_net_margin"),
    "tuned_leader_profile": dashboard.get("tuned_leader_profile"),
    "tuned_leader_pairwise_win_count": dashboard.get("tuned_leader_pairwise_win_count"),
    "tuned_leader_pairwise_loss_count": dashboard.get("tuned_leader_pairwise_loss_count"),
    "tuned_leader_total_score": dashboard.get("tuned_leader_total_score"),
    "tuned_runner_up_score_gap_to_best": dashboard.get("tuned_runner_up_score_gap_to_best"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Policy Auto-Tune Governance Dashboard Demo",
            "",
            f"- latest_effectiveness_decision: `{result['latest_effectiveness_decision']}`",
            f"- improvement_rate: `{result['improvement_rate']}`",
            f"- regression_rate: `{result['regression_rate']}`",
            f"- trend_status: `{result['trend_status']}`",
            f"- tuned_top_score_margin: `{result['tuned_top_score_margin']}`",
            f"- tuned_explanation_completeness: `{result['tuned_explanation_completeness']}`",
            f"- tuned_pairwise_net_margin: `{result['tuned_pairwise_net_margin']}`",
            f"- tuned_leader_profile: `{result['tuned_leader_profile']}`",
            f"- tuned_leader_pairwise_win_count: `{result['tuned_leader_pairwise_win_count']}`",
            f"- tuned_leader_pairwise_loss_count: `{result['tuned_leader_pairwise_loss_count']}`",
            f"- tuned_leader_total_score: `{result['tuned_leader_total_score']}`",
            f"- tuned_runner_up_score_gap_to_best: `{result['tuned_runner_up_score_gap_to_best']}`",
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
