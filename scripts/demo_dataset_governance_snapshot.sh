#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_governance_snapshot_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

if [ "${GATEFORGE_DEMO_FAST:-0}" = "1" ]; then
  mkdir -p artifacts/dataset_pipeline_demo artifacts/dataset_history_demo artifacts/dataset_policy_lifecycle_demo \
    artifacts/dataset_governance_history_demo artifacts/dataset_strategy_autotune_demo \
    artifacts/dataset_strategy_autotune_apply_history_demo artifacts/dataset_promotion_candidate_history_demo \
    artifacts/dataset_promotion_candidate_apply_history_demo artifacts/dataset_promotion_effectiveness_demo \
    artifacts/dataset_promotion_effectiveness_history_demo artifacts/dataset_failure_taxonomy_coverage_demo \
    artifacts/dataset_failure_distribution_benchmark_demo artifacts/dataset_model_scale_ladder_demo
  cat > artifacts/dataset_pipeline_demo/summary.json <<'JSON'
{"bundle_status":"PASS","build_deduplicated_cases":12,"quality_failure_case_rate":0.3}
JSON
  cat > artifacts/dataset_history_demo/history_summary.json <<'JSON'
{"total_records":4,"latest_failure_case_rate":0.3}
JSON
  cat > artifacts/dataset_history_demo/history_trend.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_policy_lifecycle_demo/ledger_summary.json <<'JSON'
{"latest_status":"PASS","total_records":4}
JSON
  cat > artifacts/dataset_governance_history_demo/trend.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_policy_lifecycle_demo/effectiveness.json <<'JSON'
{"decision":"KEEP"}
JSON
  cat > artifacts/dataset_strategy_autotune_demo/advisor.json <<'JSON'
{"advice":{"suggested_policy_profile":"dataset_default","suggested_action":"monitor"}}
JSON
  cat > artifacts/dataset_strategy_autotune_apply_history_demo/history_summary.json <<'JSON'
{"latest_final_status":"PASS","fail_rate":0.0,"needs_review_rate":0.1}
JSON
  cat > artifacts/dataset_strategy_autotune_apply_history_demo/history_trend.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_promotion_candidate_history_demo/history_summary.json <<'JSON'
{"latest_decision":"HOLD","hold_rate":0.5,"block_rate":0.0}
JSON
  cat > artifacts/dataset_promotion_candidate_history_demo/history_trend.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_promotion_candidate_apply_history_demo/history_summary.json <<'JSON'
{"latest_final_status":"PASS","fail_rate":0.0,"needs_review_rate":0.1}
JSON
  cat > artifacts/dataset_promotion_candidate_apply_history_demo/history_trend.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_promotion_effectiveness_demo/effectiveness.json <<'JSON'
{"decision":"KEEP"}
JSON
  cat > artifacts/dataset_promotion_effectiveness_history_demo/history_summary.json <<'JSON'
{"latest_decision":"KEEP","rollback_review_rate":0.0}
JSON
  cat > artifacts/dataset_promotion_effectiveness_history_demo/history_trend.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_failure_taxonomy_coverage_demo/summary.json <<'JSON'
{"status":"PASS","total_cases":12,"unique_failure_type_count":5,"missing_failure_types":[],"missing_model_scales":[],"missing_stages":[]}
JSON
  cat > artifacts/dataset_failure_distribution_benchmark_demo/summary.json <<'JSON'
{"status":"PASS","detection_rate_after":0.92,"false_positive_rate_after":0.03,"regression_rate_after":0.08,"distribution_drift_score":0.18}
JSON
  cat > artifacts/dataset_model_scale_ladder_demo/summary.json <<'JSON'
{"status":"PASS","medium_ready":true,"large_ready":true,"scale_counts":{"small":5,"medium":3,"large":2},"ci_recommendation":{"main":["small_smoke","medium_smoke"],"optional":["medium_full","large_subset"]}}
JSON
else
  bash scripts/demo_dataset_pipeline.sh >/dev/null
  bash scripts/demo_dataset_history.sh >/dev/null
  if [ ! -f artifacts/dataset_history_demo/history_summary.json ]; then
    bash scripts/demo_dataset_history.sh >/dev/null
  fi
  if [ ! -f artifacts/dataset_history_demo/history_summary.json ]; then
    echo "missing artifacts/dataset_history_demo/history_summary.json" >&2
    exit 1
  fi
  bash scripts/demo_dataset_policy_lifecycle.sh >/dev/null
  bash scripts/demo_dataset_governance_history.sh >/dev/null
  bash scripts/demo_dataset_strategy_autotune.sh >/dev/null
  bash scripts/demo_dataset_strategy_autotune_apply_history.sh >/dev/null
  bash scripts/demo_dataset_promotion_candidate_history.sh >/dev/null
  bash scripts/demo_dataset_promotion_candidate_apply_history.sh >/dev/null
  bash scripts/demo_dataset_promotion_effectiveness.sh >/dev/null
  bash scripts/demo_dataset_promotion_effectiveness_history.sh >/dev/null
  bash scripts/demo_dataset_failure_taxonomy_coverage.sh >/dev/null
  bash scripts/demo_dataset_failure_distribution_benchmark.sh >/dev/null
  bash scripts/demo_dataset_model_scale_ladder.sh >/dev/null
fi

ARGS=(
  --dataset-pipeline-summary artifacts/dataset_pipeline_demo/summary.json
  --dataset-history-summary artifacts/dataset_history_demo/history_summary.json
  --dataset-history-trend artifacts/dataset_history_demo/history_trend.json
  --dataset-governance-summary artifacts/dataset_policy_lifecycle_demo/ledger_summary.json
  --dataset-governance-trend artifacts/dataset_governance_history_demo/trend.json
  --dataset-policy-effectiveness artifacts/dataset_policy_lifecycle_demo/effectiveness.json
  --dataset-strategy-advisor artifacts/dataset_strategy_autotune_demo/advisor.json
  --dataset-strategy-apply-history artifacts/dataset_strategy_autotune_apply_history_demo/history_summary.json
  --dataset-strategy-apply-history-trend artifacts/dataset_strategy_autotune_apply_history_demo/history_trend.json
)

if [ -f artifacts/dataset_promotion_candidate_history_demo/history_summary.json ] && [ -f artifacts/dataset_promotion_candidate_history_demo/history_trend.json ]; then
  ARGS+=(--dataset-promotion-history artifacts/dataset_promotion_candidate_history_demo/history_summary.json)
  ARGS+=(--dataset-promotion-history-trend artifacts/dataset_promotion_candidate_history_demo/history_trend.json)
fi
if [ -f artifacts/dataset_promotion_candidate_apply_history_demo/history_summary.json ] && [ -f artifacts/dataset_promotion_candidate_apply_history_demo/history_trend.json ]; then
  ARGS+=(--dataset-promotion-apply-history artifacts/dataset_promotion_candidate_apply_history_demo/history_summary.json)
  ARGS+=(--dataset-promotion-apply-history-trend artifacts/dataset_promotion_candidate_apply_history_demo/history_trend.json)
fi
if [ -f artifacts/dataset_promotion_effectiveness_demo/effectiveness.json ]; then
  ARGS+=(--dataset-promotion-effectiveness artifacts/dataset_promotion_effectiveness_demo/effectiveness.json)
fi
if [ -f artifacts/dataset_promotion_effectiveness_history_demo/history_summary.json ]; then
  ARGS+=(--dataset-promotion-effectiveness-history artifacts/dataset_promotion_effectiveness_history_demo/history_summary.json)
fi
if [ -f artifacts/dataset_promotion_effectiveness_history_demo/history_trend.json ]; then
  ARGS+=(--dataset-promotion-effectiveness-history-trend artifacts/dataset_promotion_effectiveness_history_demo/history_trend.json)
fi
if [ -f artifacts/dataset_failure_taxonomy_coverage_demo/summary.json ]; then
  ARGS+=(--dataset-failure-taxonomy-coverage artifacts/dataset_failure_taxonomy_coverage_demo/summary.json)
fi
if [ -f artifacts/dataset_failure_distribution_benchmark_demo/summary.json ]; then
  ARGS+=(--dataset-failure-distribution-benchmark artifacts/dataset_failure_distribution_benchmark_demo/summary.json)
fi
if [ -f artifacts/dataset_model_scale_ladder_demo/summary.json ]; then
  ARGS+=(--dataset-model-scale-ladder artifacts/dataset_model_scale_ladder_demo/summary.json)
fi

python3 -m gateforge.dataset_governance_snapshot \
  "${ARGS[@]}" \
  --out "$OUT_DIR/summary.json" \
  --report "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_governance_snapshot_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "kpis_present": "PASS" if isinstance(payload.get("kpis"), dict) else "FAIL",
    "risks_present": "PASS" if isinstance(payload.get("risks"), list) else "FAIL",
    "promotion_effectiveness_history_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_promotion_effectiveness_history_trend_status"), (str, type(None)))
    else "FAIL",
    "failure_taxonomy_coverage_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_failure_taxonomy_coverage_status"), (str, type(None)))
    else "FAIL",
    "failure_distribution_benchmark_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_failure_distribution_benchmark_status"), (str, type(None)))
    else "FAIL",
    "model_scale_ladder_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_model_scale_ladder_status"), (str, type(None)))
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "status": payload.get("status"),
    "risks_count": len(payload.get("risks") or []),
    "promotion_effectiveness_history_trend_status": (payload.get("kpis") or {}).get(
        "dataset_promotion_effectiveness_history_trend_status"
    ),
    "promotion_effectiveness_history_latest_decision": (payload.get("kpis") or {}).get(
        "dataset_promotion_effectiveness_history_latest_decision"
    ),
    "failure_taxonomy_coverage_status": (payload.get("kpis") or {}).get("dataset_failure_taxonomy_coverage_status"),
    "failure_taxonomy_missing_model_scales_count": (payload.get("kpis") or {}).get(
        "dataset_failure_taxonomy_missing_model_scales_count"
    ),
    "failure_distribution_benchmark_status": (payload.get("kpis") or {}).get(
        "dataset_failure_distribution_benchmark_status"
    ),
    "failure_distribution_drift_score": (payload.get("kpis") or {}).get(
        "dataset_failure_distribution_drift_score"
    ),
    "model_scale_ladder_status": (payload.get("kpis") or {}).get("dataset_model_scale_ladder_status"),
    "model_scale_large_ready": (payload.get("kpis") or {}).get("dataset_model_scale_large_ready"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Governance Snapshot Demo",
            "",
            f"- status: `{summary['status']}`",
            f"- risks_count: `{summary['risks_count']}`",
            f"- promotion_effectiveness_history_trend_status: `{summary['promotion_effectiveness_history_trend_status']}`",
            f"- promotion_effectiveness_history_latest_decision: `{summary['promotion_effectiveness_history_latest_decision']}`",
            f"- failure_taxonomy_coverage_status: `{summary['failure_taxonomy_coverage_status']}`",
            f"- failure_taxonomy_missing_model_scales_count: `{summary['failure_taxonomy_missing_model_scales_count']}`",
            f"- failure_distribution_benchmark_status: `{summary['failure_distribution_benchmark_status']}`",
            f"- failure_distribution_drift_score: `{summary['failure_distribution_drift_score']}`",
            f"- model_scale_ladder_status: `{summary['model_scale_ladder_status']}`",
            f"- model_scale_large_ready: `{summary['model_scale_large_ready']}`",
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

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
