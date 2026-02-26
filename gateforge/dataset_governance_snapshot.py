from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _status_from_signals(signals: dict) -> str:
    if signals.get("dataset_pipeline_bundle_fail"):
        return "FAIL"
    if signals.get("dataset_policy_effectiveness_rollback_review"):
        return "FAIL"
    if signals.get("dataset_governance_latest_fail"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_governance_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_history_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_strategy_suggests_tighten"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_strategy_apply_latest_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_strategy_apply_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_latest_block"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_apply_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_apply_latest_fail"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_effectiveness_rollback_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_effectiveness_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_effectiveness_history_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_effectiveness_history_latest_rollback_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_failure_taxonomy_coverage_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_failure_distribution_benchmark_needs_review"):
        return "NEEDS_REVIEW"
    return "PASS"


def _compute_summary(
    dataset_pipeline: dict,
    dataset_history: dict,
    dataset_history_trend: dict,
    dataset_governance: dict,
    dataset_governance_trend: dict,
    effectiveness: dict,
    strategy_advisor: dict,
    strategy_apply_history: dict,
    strategy_apply_history_trend: dict,
    promotion_history: dict,
    promotion_history_trend: dict,
    promotion_apply_history: dict,
    promotion_apply_history_trend: dict,
    promotion_effectiveness: dict,
    promotion_effectiveness_history: dict,
    promotion_effectiveness_history_trend: dict,
    failure_taxonomy_coverage: dict,
    failure_distribution_benchmark: dict,
) -> dict:
    strategy_advice = (
        strategy_advisor.get("advice")
        if isinstance(strategy_advisor.get("advice"), dict)
        else {}
    )
    trend_alerts = (
        (dataset_governance_trend.get("trend") or {}).get("alerts")
        if isinstance(dataset_governance_trend.get("trend"), dict)
        else []
    )
    if not isinstance(trend_alerts, list):
        trend_alerts = []

    signals = {
        "dataset_pipeline_bundle_fail": str(dataset_pipeline.get("bundle_status") or "") == "FAIL",
        "dataset_governance_latest_fail": str(dataset_governance.get("latest_status") or "") == "FAIL",
        "dataset_governance_trend_needs_review": str(dataset_governance_trend.get("status") or "") == "NEEDS_REVIEW",
        "dataset_history_trend_needs_review": str(dataset_history_trend.get("status") or "") == "NEEDS_REVIEW",
        "dataset_policy_effectiveness_rollback_review": str(effectiveness.get("decision") or "") == "ROLLBACK_REVIEW",
        "dataset_strategy_suggests_tighten": str(strategy_advice.get("suggested_policy_profile") or "") == "dataset_strict",
        "dataset_strategy_apply_latest_needs_review": str(strategy_apply_history.get("latest_final_status") or "") == "NEEDS_REVIEW",
        "dataset_strategy_apply_latest_fail": str(strategy_apply_history.get("latest_final_status") or "") == "FAIL",
        "dataset_strategy_apply_trend_needs_review": str(strategy_apply_history_trend.get("status") or "") == "NEEDS_REVIEW",
        "dataset_promotion_latest_block": str(promotion_history.get("latest_decision") or "") == "BLOCK",
        "dataset_promotion_trend_needs_review": str(promotion_history_trend.get("status") or "") == "NEEDS_REVIEW",
        "dataset_promotion_apply_latest_fail": str(promotion_apply_history.get("latest_final_status") or "") == "FAIL",
        "dataset_promotion_apply_trend_needs_review": str(promotion_apply_history_trend.get("status") or "") == "NEEDS_REVIEW",
        "dataset_promotion_effectiveness_rollback_review": str(promotion_effectiveness.get("decision") or "") == "ROLLBACK_REVIEW",
        "dataset_promotion_effectiveness_needs_review": str(promotion_effectiveness.get("decision") or "") == "NEEDS_REVIEW",
        "dataset_promotion_effectiveness_history_trend_needs_review": str(
            promotion_effectiveness_history_trend.get("status") or ""
        )
        == "NEEDS_REVIEW",
        "dataset_promotion_effectiveness_history_latest_rollback_review": str(
            promotion_effectiveness_history.get("latest_decision") or ""
        )
        == "ROLLBACK_REVIEW",
        "dataset_failure_taxonomy_coverage_needs_review": str(failure_taxonomy_coverage.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_failure_distribution_benchmark_needs_review": str(failure_distribution_benchmark.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
    }
    status = _status_from_signals(signals)

    risks: list[str] = []
    if signals["dataset_pipeline_bundle_fail"]:
        risks.append("dataset_pipeline_bundle_fail")
    if signals["dataset_governance_latest_fail"]:
        risks.append("dataset_governance_latest_fail")
    if signals["dataset_governance_trend_needs_review"]:
        risks.append("dataset_governance_trend_needs_review")
    if signals["dataset_history_trend_needs_review"]:
        risks.append("dataset_history_trend_needs_review")
    if signals["dataset_policy_effectiveness_rollback_review"]:
        risks.append("dataset_policy_effectiveness_rollback_review")
    if signals["dataset_strategy_suggests_tighten"]:
        risks.append("dataset_strategy_suggests_tighten")
    if signals["dataset_strategy_apply_latest_needs_review"]:
        risks.append("dataset_strategy_apply_latest_needs_review")
    if signals["dataset_strategy_apply_latest_fail"]:
        risks.append("dataset_strategy_apply_latest_fail")
    if signals["dataset_strategy_apply_trend_needs_review"]:
        risks.append("dataset_strategy_apply_trend_needs_review")
    if signals["dataset_promotion_latest_block"]:
        risks.append("dataset_promotion_latest_block")
    if signals["dataset_promotion_trend_needs_review"]:
        risks.append("dataset_promotion_trend_needs_review")
    if signals["dataset_promotion_apply_latest_fail"]:
        risks.append("dataset_promotion_apply_latest_fail")
    if signals["dataset_promotion_apply_trend_needs_review"]:
        risks.append("dataset_promotion_apply_trend_needs_review")
    if signals["dataset_promotion_effectiveness_rollback_review"]:
        risks.append("dataset_promotion_effectiveness_rollback_review")
    if signals["dataset_promotion_effectiveness_needs_review"]:
        risks.append("dataset_promotion_effectiveness_needs_review")
    if signals["dataset_promotion_effectiveness_history_trend_needs_review"]:
        risks.append("dataset_promotion_effectiveness_history_trend_needs_review")
    if signals["dataset_promotion_effectiveness_history_latest_rollback_review"]:
        risks.append("dataset_promotion_effectiveness_history_latest_rollback_review")
    if signals["dataset_failure_taxonomy_coverage_needs_review"]:
        risks.append("dataset_failure_taxonomy_coverage_needs_review")
    if signals["dataset_failure_distribution_benchmark_needs_review"]:
        risks.append("dataset_failure_distribution_benchmark_needs_review")

    missing_failure_types = failure_taxonomy_coverage.get("missing_failure_types", [])
    if not isinstance(missing_failure_types, list):
        missing_failure_types = []
    missing_model_scales = failure_taxonomy_coverage.get("missing_model_scales", [])
    if not isinstance(missing_model_scales, list):
        missing_model_scales = []
    missing_stages = failure_taxonomy_coverage.get("missing_stages", [])
    if not isinstance(missing_stages, list):
        missing_stages = []

    kpis = {
        "dataset_pipeline_deduplicated_cases": _to_int(
            dataset_pipeline.get(
                "build_deduplicated_cases",
                dataset_pipeline.get("deduplicated_cases", dataset_pipeline.get("total_cases", 0)),
            )
        ),
        "dataset_pipeline_failure_case_rate": _to_float(
            dataset_pipeline.get("quality_failure_case_rate", dataset_pipeline.get("failure_case_rate", 0.0))
        ),
        "dataset_history_total_records": _to_int(dataset_history.get("total_records", 0)),
        "dataset_history_latest_failure_case_rate": _to_float(dataset_history.get("latest_failure_case_rate", 0.0)),
        "dataset_governance_total_records": _to_int(dataset_governance.get("total_records", 0)),
        "dataset_governance_latest_status": dataset_governance.get("latest_status"),
        "dataset_governance_trend_alert_count": len(trend_alerts),
        "dataset_policy_effectiveness_decision": effectiveness.get("decision"),
        "dataset_strategy_profile": strategy_advice.get("suggested_policy_profile"),
        "dataset_strategy_action": strategy_advice.get("suggested_action"),
        "dataset_strategy_apply_latest_final_status": strategy_apply_history.get("latest_final_status"),
        "dataset_strategy_apply_fail_rate": _to_float(strategy_apply_history.get("fail_rate", 0.0)),
        "dataset_strategy_apply_needs_review_rate": _to_float(strategy_apply_history.get("needs_review_rate", 0.0)),
        "dataset_strategy_apply_trend_status": strategy_apply_history_trend.get("status"),
        "dataset_promotion_latest_decision": promotion_history.get("latest_decision"),
        "dataset_promotion_hold_rate": _to_float(promotion_history.get("hold_rate", 0.0)),
        "dataset_promotion_block_rate": _to_float(promotion_history.get("block_rate", 0.0)),
        "dataset_promotion_trend_status": promotion_history_trend.get("status"),
        "dataset_promotion_apply_latest_final_status": promotion_apply_history.get("latest_final_status"),
        "dataset_promotion_apply_fail_rate": _to_float(promotion_apply_history.get("fail_rate", 0.0)),
        "dataset_promotion_apply_needs_review_rate": _to_float(promotion_apply_history.get("needs_review_rate", 0.0)),
        "dataset_promotion_apply_trend_status": promotion_apply_history_trend.get("status"),
        "dataset_promotion_effectiveness_decision": promotion_effectiveness.get("decision"),
        "dataset_promotion_effectiveness_history_latest_decision": promotion_effectiveness_history.get("latest_decision"),
        "dataset_promotion_effectiveness_history_trend_status": promotion_effectiveness_history_trend.get("status"),
        "dataset_failure_taxonomy_coverage_status": failure_taxonomy_coverage.get("status"),
        "dataset_failure_taxonomy_total_cases": _to_int(failure_taxonomy_coverage.get("total_cases", 0)),
        "dataset_failure_taxonomy_unique_failure_types": _to_int(
            failure_taxonomy_coverage.get("unique_failure_type_count", 0)
        ),
        "dataset_failure_taxonomy_missing_failure_types_count": len(missing_failure_types),
        "dataset_failure_taxonomy_missing_model_scales_count": len(missing_model_scales),
        "dataset_failure_taxonomy_missing_stages_count": len(missing_stages),
        "dataset_failure_distribution_benchmark_status": failure_distribution_benchmark.get("status"),
        "dataset_failure_distribution_detection_rate_after": _to_float(
            failure_distribution_benchmark.get("detection_rate_after", 0.0)
        ),
        "dataset_failure_distribution_false_positive_rate_after": _to_float(
            failure_distribution_benchmark.get("false_positive_rate_after", 0.0)
        ),
        "dataset_failure_distribution_regression_rate_after": _to_float(
            failure_distribution_benchmark.get("regression_rate_after", 0.0)
        ),
        "dataset_failure_distribution_drift_score": _to_float(
            failure_distribution_benchmark.get("distribution_drift_score", 0.0)
        ),
    }
    return {
        "status": status,
        "signals": signals,
        "risks": risks,
        "kpis": kpis,
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    kpis = summary.get("kpis", {})
    lines = [
        "# GateForge Dataset Governance Snapshot",
        "",
        f"- status: `{summary.get('status')}`",
        f"- dataset_pipeline_deduplicated_cases: `{kpis.get('dataset_pipeline_deduplicated_cases')}`",
        f"- dataset_pipeline_failure_case_rate: `{kpis.get('dataset_pipeline_failure_case_rate')}`",
        f"- dataset_history_total_records: `{kpis.get('dataset_history_total_records')}`",
        f"- dataset_governance_total_records: `{kpis.get('dataset_governance_total_records')}`",
        f"- dataset_policy_effectiveness_decision: `{kpis.get('dataset_policy_effectiveness_decision')}`",
        f"- dataset_strategy_profile: `{kpis.get('dataset_strategy_profile')}`",
        f"- dataset_strategy_action: `{kpis.get('dataset_strategy_action')}`",
        f"- dataset_strategy_apply_latest_final_status: `{kpis.get('dataset_strategy_apply_latest_final_status')}`",
        f"- dataset_strategy_apply_fail_rate: `{kpis.get('dataset_strategy_apply_fail_rate')}`",
        f"- dataset_strategy_apply_needs_review_rate: `{kpis.get('dataset_strategy_apply_needs_review_rate')}`",
        f"- dataset_strategy_apply_trend_status: `{kpis.get('dataset_strategy_apply_trend_status')}`",
        f"- dataset_promotion_latest_decision: `{kpis.get('dataset_promotion_latest_decision')}`",
        f"- dataset_promotion_hold_rate: `{kpis.get('dataset_promotion_hold_rate')}`",
        f"- dataset_promotion_block_rate: `{kpis.get('dataset_promotion_block_rate')}`",
        f"- dataset_promotion_trend_status: `{kpis.get('dataset_promotion_trend_status')}`",
        f"- dataset_promotion_apply_latest_final_status: `{kpis.get('dataset_promotion_apply_latest_final_status')}`",
        f"- dataset_promotion_apply_fail_rate: `{kpis.get('dataset_promotion_apply_fail_rate')}`",
        f"- dataset_promotion_apply_needs_review_rate: `{kpis.get('dataset_promotion_apply_needs_review_rate')}`",
        f"- dataset_promotion_apply_trend_status: `{kpis.get('dataset_promotion_apply_trend_status')}`",
        f"- dataset_promotion_effectiveness_decision: `{kpis.get('dataset_promotion_effectiveness_decision')}`",
        f"- dataset_promotion_effectiveness_history_latest_decision: `{kpis.get('dataset_promotion_effectiveness_history_latest_decision')}`",
        f"- dataset_promotion_effectiveness_history_trend_status: `{kpis.get('dataset_promotion_effectiveness_history_trend_status')}`",
        f"- dataset_failure_taxonomy_coverage_status: `{kpis.get('dataset_failure_taxonomy_coverage_status')}`",
        f"- dataset_failure_taxonomy_total_cases: `{kpis.get('dataset_failure_taxonomy_total_cases')}`",
        f"- dataset_failure_taxonomy_unique_failure_types: `{kpis.get('dataset_failure_taxonomy_unique_failure_types')}`",
        f"- dataset_failure_taxonomy_missing_failure_types_count: `{kpis.get('dataset_failure_taxonomy_missing_failure_types_count')}`",
        f"- dataset_failure_taxonomy_missing_model_scales_count: `{kpis.get('dataset_failure_taxonomy_missing_model_scales_count')}`",
        f"- dataset_failure_taxonomy_missing_stages_count: `{kpis.get('dataset_failure_taxonomy_missing_stages_count')}`",
        f"- dataset_failure_distribution_benchmark_status: `{kpis.get('dataset_failure_distribution_benchmark_status')}`",
        f"- dataset_failure_distribution_detection_rate_after: `{kpis.get('dataset_failure_distribution_detection_rate_after')}`",
        f"- dataset_failure_distribution_false_positive_rate_after: `{kpis.get('dataset_failure_distribution_false_positive_rate_after')}`",
        f"- dataset_failure_distribution_regression_rate_after: `{kpis.get('dataset_failure_distribution_regression_rate_after')}`",
        f"- dataset_failure_distribution_drift_score: `{kpis.get('dataset_failure_distribution_drift_score')}`",
        "",
        "## Risks",
        "",
    ]
    risks = summary.get("risks", [])
    if isinstance(risks, list) and risks:
        for r in risks:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Sources", ""])
    sources = summary.get("sources", {})
    for k, v in sources.items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build dataset governance snapshot from dataset governance artifacts")
    parser.add_argument("--dataset-pipeline-summary", default=None, help="Path to dataset pipeline summary JSON")
    parser.add_argument("--dataset-history-summary", default=None, help="Path to dataset history summary JSON")
    parser.add_argument("--dataset-history-trend", default=None, help="Path to dataset history trend JSON")
    parser.add_argument("--dataset-governance-summary", default=None, help="Path to dataset governance ledger summary JSON")
    parser.add_argument("--dataset-governance-trend", default=None, help="Path to dataset governance trend JSON")
    parser.add_argument("--dataset-policy-effectiveness", default=None, help="Path to dataset policy effectiveness JSON")
    parser.add_argument("--dataset-strategy-advisor", default=None, help="Path to dataset strategy advisor JSON")
    parser.add_argument(
        "--dataset-strategy-apply-history",
        default=None,
        help="Path to dataset strategy apply history summary JSON",
    )
    parser.add_argument(
        "--dataset-strategy-apply-history-trend",
        default=None,
        help="Path to dataset strategy apply history trend JSON",
    )
    parser.add_argument(
        "--dataset-promotion-history",
        default=None,
        help="Path to dataset promotion candidate history summary JSON",
    )
    parser.add_argument(
        "--dataset-promotion-history-trend",
        default=None,
        help="Path to dataset promotion candidate history trend JSON",
    )
    parser.add_argument(
        "--dataset-promotion-apply-history",
        default=None,
        help="Path to dataset promotion apply history summary JSON",
    )
    parser.add_argument(
        "--dataset-promotion-apply-history-trend",
        default=None,
        help="Path to dataset promotion apply history trend JSON",
    )
    parser.add_argument(
        "--dataset-promotion-effectiveness",
        default=None,
        help="Path to dataset promotion effectiveness summary JSON",
    )
    parser.add_argument(
        "--dataset-promotion-effectiveness-history",
        default=None,
        help="Path to dataset promotion effectiveness history summary JSON",
    )
    parser.add_argument(
        "--dataset-promotion-effectiveness-history-trend",
        default=None,
        help="Path to dataset promotion effectiveness history trend JSON",
    )
    parser.add_argument(
        "--dataset-failure-taxonomy-coverage",
        default=None,
        help="Path to dataset failure taxonomy coverage summary JSON",
    )
    parser.add_argument(
        "--dataset-failure-distribution-benchmark",
        default=None,
        help="Path to dataset failure distribution benchmark summary JSON",
    )
    parser.add_argument("--out", default="artifacts/dataset_governance_snapshot/summary.json", help="Output JSON path")
    parser.add_argument("--report", default=None, help="Output markdown path")
    args = parser.parse_args()

    dataset_pipeline = _load_json(args.dataset_pipeline_summary)
    dataset_history = _load_json(args.dataset_history_summary)
    dataset_history_trend = _load_json(args.dataset_history_trend)
    dataset_governance = _load_json(args.dataset_governance_summary)
    dataset_governance_trend = _load_json(args.dataset_governance_trend)
    effectiveness = _load_json(args.dataset_policy_effectiveness)
    strategy_advisor = _load_json(args.dataset_strategy_advisor)
    strategy_apply_history = _load_json(args.dataset_strategy_apply_history)
    strategy_apply_history_trend = _load_json(args.dataset_strategy_apply_history_trend)
    promotion_history = _load_json(args.dataset_promotion_history)
    promotion_history_trend = _load_json(args.dataset_promotion_history_trend)
    promotion_apply_history = _load_json(args.dataset_promotion_apply_history)
    promotion_apply_history_trend = _load_json(args.dataset_promotion_apply_history_trend)
    promotion_effectiveness = _load_json(args.dataset_promotion_effectiveness)
    promotion_effectiveness_history = _load_json(args.dataset_promotion_effectiveness_history)
    promotion_effectiveness_history_trend = _load_json(args.dataset_promotion_effectiveness_history_trend)
    failure_taxonomy_coverage = _load_json(args.dataset_failure_taxonomy_coverage)
    failure_distribution_benchmark = _load_json(args.dataset_failure_distribution_benchmark)

    summary = _compute_summary(
        dataset_pipeline,
        dataset_history,
        dataset_history_trend,
        dataset_governance,
        dataset_governance_trend,
        effectiveness,
        strategy_advisor,
        strategy_apply_history,
        strategy_apply_history_trend,
        promotion_history,
        promotion_history_trend,
        promotion_apply_history,
        promotion_apply_history_trend,
        promotion_effectiveness,
        promotion_effectiveness_history,
        promotion_effectiveness_history_trend,
        failure_taxonomy_coverage,
        failure_distribution_benchmark,
    )
    summary["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    summary["sources"] = {
        "dataset_pipeline_summary_path": args.dataset_pipeline_summary,
        "dataset_history_summary_path": args.dataset_history_summary,
        "dataset_history_trend_path": args.dataset_history_trend,
        "dataset_governance_summary_path": args.dataset_governance_summary,
        "dataset_governance_trend_path": args.dataset_governance_trend,
        "dataset_policy_effectiveness_path": args.dataset_policy_effectiveness,
        "dataset_strategy_advisor_path": args.dataset_strategy_advisor,
        "dataset_strategy_apply_history_path": args.dataset_strategy_apply_history,
        "dataset_strategy_apply_history_trend_path": args.dataset_strategy_apply_history_trend,
        "dataset_promotion_history_path": args.dataset_promotion_history,
        "dataset_promotion_history_trend_path": args.dataset_promotion_history_trend,
        "dataset_promotion_apply_history_path": args.dataset_promotion_apply_history,
        "dataset_promotion_apply_history_trend_path": args.dataset_promotion_apply_history_trend,
        "dataset_promotion_effectiveness_path": args.dataset_promotion_effectiveness,
        "dataset_promotion_effectiveness_history_path": args.dataset_promotion_effectiveness_history,
        "dataset_promotion_effectiveness_history_trend_path": args.dataset_promotion_effectiveness_history_trend,
        "dataset_failure_taxonomy_coverage_path": args.dataset_failure_taxonomy_coverage,
        "dataset_failure_distribution_benchmark_path": args.dataset_failure_distribution_benchmark,
    }

    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "risks": summary.get("risks", [])}))

    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
