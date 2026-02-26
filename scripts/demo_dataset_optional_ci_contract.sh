#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_optional_ci_contract_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

if [ "${GATEFORGE_DEMO_FAST:-0}" = "1" ]; then
  python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts")
mapping = {
    "dataset_pipeline_demo/summary.json": {"bundle_status": "PASS", "result_flags": {}},
    "dataset_artifacts_pipeline_demo/summary.json": {"bundle_status": "PASS", "quality_gate_status": "PASS"},
    "dataset_history_demo/summary.json": {"bundle_status": "PASS"},
    "dataset_governance_demo/summary.json": {"bundle_status": "PASS"},
    "dataset_policy_lifecycle_demo/summary.json": {"bundle_status": "PASS"},
    "dataset_governance_history_demo/summary.json": {"bundle_status": "PASS"},
    "dataset_strategy_autotune_demo/summary.json": {"bundle_status": "PASS"},
    "dataset_strategy_autotune_apply_demo/summary.json": {"bundle_status": "PASS"},
    "dataset_strategy_autotune_apply_history_demo/summary.json": {"bundle_status": "PASS"},
    "dataset_governance_snapshot_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "promotion_effectiveness_history_trend_status": "PASS",
        "failure_taxonomy_coverage_status": "PASS",
        "failure_taxonomy_missing_model_scales_count": 0,
        "failure_distribution_benchmark_status": "PASS",
        "failure_distribution_drift_score": 0.12,
        "model_scale_ladder_status": "PASS",
        "model_scale_large_ready": True,
    },
    "dataset_governance_snapshot_trend_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "status_transition": "PASS->PASS",
        "promotion_effectiveness_history_trend_transition": "PASS->PASS",
        "failure_taxonomy_coverage_status_transition": "PASS->PASS",
        "failure_distribution_benchmark_status_transition": "PASS->PASS",
        "model_scale_ladder_status_transition": "PASS->PASS",
        "status_delta_alert_count": 0,
        "severity_level": "low",
    },
    "dataset_failure_taxonomy_coverage_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "coverage_status": "PASS",
        "missing_model_scales_count": 0,
    },
    "dataset_failure_distribution_benchmark_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "benchmark_status": "PASS",
        "distribution_drift_score": 0.1,
    },
    "dataset_model_scale_ladder_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "ladder_status": "PASS",
        "large_ready": True,
    },
    "dataset_promotion_candidate_demo/summary.json": {"bundle_status": "PASS", "decision": "HOLD"},
    "dataset_promotion_candidate_apply_demo/summary.json": {"bundle_status": "PASS"},
    "dataset_promotion_candidate_history_demo/summary.json": {"bundle_status": "PASS"},
    "dataset_promotion_candidate_apply_history_demo/summary.json": {"bundle_status": "PASS"},
    "dataset_promotion_effectiveness_demo/summary.json": {"bundle_status": "PASS", "effectiveness_decision": "KEEP"},
    "dataset_promotion_effectiveness_history_demo/summary.json": {"bundle_status": "PASS", "trend_status": "PASS"},
    "dataset_policy_autotune_history_demo/summary.json": {"bundle_status": "PASS"},
}
for rel, payload in mapping.items():
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), encoding="utf-8")
PY
else
  bash scripts/demo_dataset_pipeline.sh >/dev/null
  bash scripts/demo_dataset_artifacts_pipeline.sh >/dev/null
  bash scripts/demo_dataset_history.sh >/dev/null
  bash scripts/demo_dataset_governance.sh >/dev/null
  bash scripts/demo_dataset_policy_lifecycle.sh >/dev/null
  bash scripts/demo_dataset_governance_history.sh >/dev/null
  bash scripts/demo_dataset_strategy_autotune.sh >/dev/null
  bash scripts/demo_dataset_strategy_autotune_apply.sh >/dev/null
  bash scripts/demo_dataset_strategy_autotune_apply_history.sh >/dev/null
  bash scripts/demo_dataset_governance_snapshot.sh >/dev/null
  bash scripts/demo_dataset_governance_snapshot_trend.sh >/dev/null
  bash scripts/demo_dataset_failure_taxonomy_coverage.sh >/dev/null
  bash scripts/demo_dataset_failure_distribution_benchmark.sh >/dev/null
  bash scripts/demo_dataset_model_scale_ladder.sh >/dev/null
  bash scripts/demo_dataset_promotion_candidate.sh >/dev/null
  bash scripts/demo_dataset_promotion_candidate_apply.sh >/dev/null
  bash scripts/demo_dataset_promotion_candidate_history.sh >/dev/null
  bash scripts/demo_dataset_promotion_candidate_apply_history.sh >/dev/null
  bash scripts/demo_dataset_promotion_effectiveness.sh >/dev/null
  bash scripts/demo_dataset_promotion_effectiveness_history.sh >/dev/null
  bash scripts/demo_dataset_policy_autotune_history.sh >/dev/null
fi

python3 -m gateforge.dataset_optional_ci_contract \
  --artifacts-root artifacts \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_optional_ci_contract_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
checks = payload.get("checks", [])
flags = {
    "contract_status_pass": "PASS" if payload.get("status") == "PASS" else "FAIL",
    "required_summary_count_present": "PASS" if int(payload.get("required_summary_count", 0) or 0) >= 10 else "FAIL",
    "checks_non_empty": "PASS" if isinstance(checks, list) and len(checks) > 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "contract_status": payload.get("status"),
    "required_summary_count": payload.get("required_summary_count"),
    "fail_count": payload.get("fail_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Optional CI Contract Demo",
            "",
            f"- contract_status: `{demo['contract_status']}`",
            f"- required_summary_count: `{demo['required_summary_count']}`",
            f"- fail_count: `{demo['fail_count']}`",
            f"- bundle_status: `{demo['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
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
