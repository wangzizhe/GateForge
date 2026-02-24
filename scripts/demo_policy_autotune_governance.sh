#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/policy_autotune_governance_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

bash scripts/demo_policy_autotune.sh >/dev/null
bash scripts/demo_governance_snapshot_from_orchestrate_compare.sh >/dev/null

python3 -m gateforge.policy_autotune_promote_flow \
  --snapshot artifacts/governance_snapshot_orchestrate_demo/summary.json \
  --advisor artifacts/policy_autotune_demo/advisor.json \
  --out-dir "$OUT_DIR" \
  --out "$OUT_DIR/flow_summary.json" \
  --report "$OUT_DIR/flow_summary.md"

python3 -m gateforge.policy_autotune_effectiveness \
  --flow-summary "$OUT_DIR/flow_summary.json" \
  --out "$OUT_DIR/effectiveness.json" \
  --report-out "$OUT_DIR/effectiveness.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/policy_autotune_governance_demo")
flow = json.loads((out / "flow_summary.json").read_text(encoding="utf-8"))
eff = json.loads((out / "effectiveness.json").read_text(encoding="utf-8"))

flags = {
    "baseline_apply_status_present": "PASS" if flow.get("baseline", {}).get("apply_status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "tuned_apply_status_present": "PASS" if flow.get("tuned", {}).get("apply_status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "effectiveness_decision_present": "PASS" if eff.get("decision") in {"IMPROVED", "UNCHANGED", "REGRESSED"} else "FAIL",
    "quality_delta_present": "PASS"
    if isinstance(eff.get("delta_top_score_margin"), int)
    and isinstance(eff.get("delta_explanation_completeness"), int)
    and isinstance(eff.get("delta_pairwise_net_margin"), int)
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "advisor_profile": flow.get("advisor_profile"),
    "baseline_compare_status": flow.get("baseline", {}).get("compare_status"),
    "tuned_compare_status": flow.get("tuned", {}).get("compare_status"),
    "baseline_apply_status": flow.get("baseline", {}).get("apply_status"),
    "tuned_apply_status": flow.get("tuned", {}).get("apply_status"),
    "effectiveness_decision": eff.get("decision"),
    "delta_apply_score": eff.get("delta_apply_score"),
    "delta_compare_score": eff.get("delta_compare_score"),
    "delta_top_score_margin": eff.get("delta_top_score_margin"),
    "delta_explanation_completeness": eff.get("delta_explanation_completeness"),
    "delta_pairwise_net_margin": eff.get("delta_pairwise_net_margin"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Policy Auto-Tune Governance Demo",
            "",
            f"- advisor_profile: `{summary['advisor_profile']}`",
            f"- baseline_compare_status: `{summary['baseline_compare_status']}`",
            f"- tuned_compare_status: `{summary['tuned_compare_status']}`",
            f"- baseline_apply_status: `{summary['baseline_apply_status']}`",
            f"- tuned_apply_status: `{summary['tuned_apply_status']}`",
            f"- effectiveness_decision: `{summary['effectiveness_decision']}`",
            f"- delta_apply_score: `{summary['delta_apply_score']}`",
            f"- delta_compare_score: `{summary['delta_compare_score']}`",
            f"- delta_top_score_margin: `{summary['delta_top_score_margin']}`",
            f"- delta_explanation_completeness: `{summary['delta_explanation_completeness']}`",
            f"- delta_pairwise_net_margin: `{summary['delta_pairwise_net_margin']}`",
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
print(json.dumps({"bundle_status": bundle_status, "effectiveness_decision": summary["effectiveness_decision"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
