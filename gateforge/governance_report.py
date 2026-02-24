from __future__ import annotations

import argparse
import json
from pathlib import Path


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _status_from_signals(signals: dict) -> str:
    if signals.get("matrix_status") == "FAIL":
        return "FAIL"
    if signals.get("mutation_compare_failed"):
        return "NEEDS_REVIEW"
    if signals.get("advisor_history_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("advisor_history_rollback_rate_high"):
        return "NEEDS_REVIEW"
    if signals.get("advisor_history_latest_action_rollback_review"):
        return "NEEDS_REVIEW"
    if signals.get("advisor_history_top_driver_recommended_component_dominant"):
        return "NEEDS_REVIEW"
    if signals.get("advisor_history_dominant_top_driver_changed"):
        return "NEEDS_REVIEW"
    if signals.get("runtime_ledger_fail_rate_high"):
        return "NEEDS_REVIEW"
    if signals.get("runtime_ledger_needs_review_rate_high"):
        return "NEEDS_REVIEW"
    if signals.get("mutation_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("invariant_repair_compare_status") == "FAIL":
        return "NEEDS_REVIEW"
    if signals.get("strategy_switch_recommended"):
        return "NEEDS_REVIEW"
    if signals.get("invariant_repair_switch_recommended"):
        return "NEEDS_REVIEW"
    if signals.get("repair_compare_has_downgrade"):
        return "NEEDS_REVIEW"
    if signals.get("strict_non_pass_rate", 0.0) >= 0.5:
        return "NEEDS_REVIEW"
    return "PASS"


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _extract_repair_compare(repair: dict) -> dict:
    if not isinstance(repair, dict):
        return {}
    profile_compare = repair.get("profile_compare")
    if isinstance(profile_compare, dict):
        return profile_compare

    strategy_compare = repair.get("strategy_compare")
    if not isinstance(strategy_compare, dict):
        return {}

    relation = str(strategy_compare.get("relation") or "").lower()
    downgrade_count = 1 if relation == "downgraded" else 0
    strict_downgrade_rate = 1.0 if relation == "downgraded" else 0.0
    return {
        "from_policy_profile": strategy_compare.get("from_profile"),
        "to_policy_profile": strategy_compare.get("to_profile"),
        "recommended_profile": strategy_compare.get("recommended_profile"),
        "downgrade_count": downgrade_count,
        "strict_downgrade_rate": strict_downgrade_rate,
        "strategy_compare_relation": strategy_compare.get("relation"),
    }


def _extract_invariant_compare(invariant: dict) -> dict:
    if not isinstance(invariant, dict):
        return {}
    best_profile = invariant.get("best_profile")
    ranking = invariant.get("ranking")
    if not isinstance(best_profile, str):
        return {}
    profile_results = invariant.get("profile_results")
    if not isinstance(profile_results, list):
        profile_results = []
    from_profile = None
    for row in profile_results:
        if isinstance(row, dict) and isinstance(row.get("profile"), str):
            from_profile = str(row["profile"])
            break
    top_margin = None
    if isinstance(ranking, list) and len(ranking) >= 2:
        first = ranking[0]
        second = ranking[1]
        if isinstance(first, dict) and isinstance(second, dict):
            try:
                top_margin = int(first.get("total_score", 0)) - int(second.get("total_score", 0))
            except (TypeError, ValueError):
                top_margin = None
    return {
        "status": invariant.get("status"),
        "from_profile": from_profile,
        "best_profile": best_profile,
        "best_reason": invariant.get("best_reason"),
        "best_total_score": invariant.get("best_total_score"),
        "top_score_margin": top_margin,
    }


def _compute_trend(current: dict, previous: dict) -> dict:
    current_status = str(current.get("status") or "UNKNOWN")
    prev_status = str(previous.get("status") or "UNKNOWN")
    transition = f"{prev_status}->{current_status}"

    current_risks = set(r for r in current.get("risks", []) if isinstance(r, str))
    prev_risks = set(r for r in previous.get("risks", []) if isinstance(r, str))

    current_kpis = current.get("kpis", {}) if isinstance(current.get("kpis"), dict) else {}
    prev_kpis = previous.get("kpis", {}) if isinstance(previous.get("kpis"), dict) else {}

    return {
        "status_transition": transition,
        "new_risks": sorted(current_risks - prev_risks),
        "resolved_risks": sorted(prev_risks - current_risks),
        "kpi_delta": {
            "strict_downgrade_rate_delta": round(
                _to_float(current_kpis.get("strict_downgrade_rate")) - _to_float(prev_kpis.get("strict_downgrade_rate")),
                4,
            ),
            "review_recovery_rate_delta": round(
                _to_float(current_kpis.get("review_recovery_rate")) - _to_float(prev_kpis.get("review_recovery_rate")),
                4,
            ),
            "strict_non_pass_rate_delta": round(
                _to_float(current_kpis.get("strict_non_pass_rate")) - _to_float(prev_kpis.get("strict_non_pass_rate")),
                4,
            ),
            "approval_rate_delta": round(
                _to_float(current_kpis.get("approval_rate")) - _to_float(prev_kpis.get("approval_rate")),
                4,
            ),
            "fail_rate_delta": round(
                _to_float(current_kpis.get("fail_rate")) - _to_float(prev_kpis.get("fail_rate")),
                4,
            ),
            "strategy_compare_relation_transition": f"{current_kpis.get('strategy_compare_relation')}<-{prev_kpis.get('strategy_compare_relation')}",
            "recommended_profile_transition": f"{current_kpis.get('recommended_profile')}<-{prev_kpis.get('recommended_profile')}",
        },
    }


def _extract_mutation(mutation: dict) -> dict:
    if not isinstance(mutation, dict):
        return {}
    return {
        "bundle_status": str(mutation.get("bundle_status") or "UNKNOWN"),
        "latest_match_rate": _to_float(mutation.get("latest_match_rate"), 0.0),
        "latest_gate_pass_rate": _to_float(mutation.get("latest_gate_pass_rate"), 0.0),
        "trend_status": str(mutation.get("trend_status") or "UNKNOWN"),
        "compare_decision": str(mutation.get("compare_decision") or "UNKNOWN"),
    }


def _extract_policy_autotune_advisor_history(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}
    return {
        "bundle_status": str(payload.get("bundle_status") or "UNKNOWN"),
        "latest_action": str(payload.get("latest_action") or "UNKNOWN"),
        "tighten_rate": _to_float(payload.get("tighten_rate"), 0.0),
        "rollback_review_rate": _to_float(payload.get("rollback_review_rate"), 0.0),
        "trend_status": str(payload.get("trend_status") or "UNKNOWN"),
        "latest_top_driver": (
            str(payload.get("latest_top_driver"))
            if isinstance(payload.get("latest_top_driver"), str)
            else None
        ),
        "top_driver_non_null_rate": _to_float(payload.get("top_driver_non_null_rate"), 0.0),
        "trend_alerts": (
            payload.get("trend_alerts")
            if isinstance(payload.get("trend_alerts"), list)
            else []
        ),
    }


def _extract_runtime_ledger(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}
    kpis = payload.get("kpis", {}) if isinstance(payload.get("kpis"), dict) else {}
    return {
        "total_records": int(payload.get("total_records", 0) or 0),
        "pass_rate": _to_float(kpis.get("pass_rate"), 0.0),
        "fail_rate": _to_float(kpis.get("fail_rate"), 0.0),
        "needs_review_rate": _to_float(kpis.get("needs_review_rate"), 0.0),
    }


def _compute_summary(
    repair: dict,
    review: dict,
    matrix: dict,
    invariant_compare: dict,
    mutation_dashboard: dict,
    policy_autotune_advisor_history: dict,
    runtime_ledger_summary: dict,
) -> dict:
    repair_compare = _extract_repair_compare(repair)
    invariant = _extract_invariant_compare(invariant_compare)
    mutation = _extract_mutation(mutation_dashboard)
    advisor_history = _extract_policy_autotune_advisor_history(policy_autotune_advisor_history)
    runtime_ledger = _extract_runtime_ledger(runtime_ledger_summary)
    kpis = review.get("kpis", {}) if isinstance(review, dict) else {}

    strict_non_pass_rate = float(kpis.get("strict_non_pass_rate", 0.0) or 0.0)
    review_recovery_rate = float(kpis.get("review_recovery_rate", 0.0) or 0.0)
    downgrade_count = int(repair_compare.get("downgrade_count", 0) or 0)
    compare_from = repair_compare.get("from_policy_profile")
    recommended_profile = repair_compare.get("recommended_profile")
    strategy_switch_recommended = bool(
        isinstance(compare_from, str)
        and isinstance(recommended_profile, str)
        and compare_from
        and recommended_profile
        and compare_from != recommended_profile
    )
    invariant_from_profile = invariant.get("from_profile")
    invariant_best_profile = invariant.get("best_profile")
    invariant_switch_recommended = bool(
        isinstance(invariant_from_profile, str)
        and isinstance(invariant_best_profile, str)
        and invariant_from_profile
        and invariant_best_profile
        and invariant_from_profile != invariant_best_profile
    )

    mutation_match_rate = float(mutation.get("latest_match_rate", 0.0) or 0.0)
    mutation_gate_pass_rate = float(mutation.get("latest_gate_pass_rate", 0.0) or 0.0)
    mutation_trend_status = str(mutation.get("trend_status") or "UNKNOWN")
    mutation_compare_decision = str(mutation.get("compare_decision") or "UNKNOWN")
    advisor_history_trend_status = str(advisor_history.get("trend_status") or "UNKNOWN")
    advisor_history_latest_action = str(advisor_history.get("latest_action") or "UNKNOWN")
    advisor_history_rollback_rate = float(advisor_history.get("rollback_review_rate", 0.0) or 0.0)
    advisor_history_tighten_rate = float(advisor_history.get("tighten_rate", 0.0) or 0.0)
    advisor_history_latest_top_driver = (
        str(advisor_history.get("latest_top_driver"))
        if isinstance(advisor_history.get("latest_top_driver"), str)
        else None
    )
    advisor_history_top_driver_non_null_rate = float(advisor_history.get("top_driver_non_null_rate", 0.0) or 0.0)
    advisor_history_trend_alerts = advisor_history.get("trend_alerts") if isinstance(advisor_history.get("trend_alerts"), list) else []

    signals = {
        "matrix_status": matrix.get("matrix_status", "UNKNOWN"),
        "repair_compare_has_downgrade": downgrade_count > 0,
        "strategy_switch_recommended": strategy_switch_recommended,
        "invariant_repair_switch_recommended": invariant_switch_recommended,
        "invariant_repair_compare_status": str(invariant.get("status") or "UNKNOWN"),
        "strict_non_pass_rate": strict_non_pass_rate,
        "review_recovery_rate": review_recovery_rate,
        "mutation_trend_needs_review": mutation_trend_status == "NEEDS_REVIEW",
        "mutation_compare_failed": mutation_compare_decision == "FAIL",
        "advisor_history_trend_needs_review": advisor_history_trend_status == "NEEDS_REVIEW",
        "advisor_history_rollback_rate_high": advisor_history_rollback_rate >= 0.3,
        "advisor_history_latest_action_rollback_review": advisor_history_latest_action == "ROLLBACK_REVIEW",
        "advisor_history_top_driver_recommended_component_dominant": (
            advisor_history_latest_top_driver == "component_delta:recommended_component"
            and advisor_history_top_driver_non_null_rate >= 0.5
        ),
        "advisor_history_dominant_top_driver_changed": (
            any(str(a) == "dominant_top_driver_changed" for a in advisor_history_trend_alerts)
        ),
        "runtime_ledger_fail_rate_high": runtime_ledger.get("fail_rate", 0.0) >= 0.3,
        "runtime_ledger_needs_review_rate_high": runtime_ledger.get("needs_review_rate", 0.0) >= 0.4,
    }

    status = _status_from_signals(signals)

    risks = []
    if signals["matrix_status"] == "FAIL":
        risks.append("ci_matrix_failed")
    if downgrade_count > 0:
        risks.append("strict_profile_downgrade_detected")
    if strict_non_pass_rate >= 0.5:
        risks.append("strict_non_pass_rate_high")
    if review_recovery_rate < 0.5:
        risks.append("review_recovery_rate_low")
    if strategy_switch_recommended:
        risks.append("strategy_profile_switch_recommended")
    if invariant_switch_recommended:
        risks.append("invariant_repair_profile_switch_recommended")
    if str(invariant.get("status") or "").upper() == "FAIL":
        risks.append("invariant_repair_compare_failed")
    if signals["mutation_trend_needs_review"]:
        risks.append("mutation_trend_needs_review")
    if signals["mutation_compare_failed"]:
        risks.append("mutation_compare_regressed")
    if mutation_match_rate < 0.98:
        risks.append("mutation_match_rate_below_target")
    if mutation_gate_pass_rate < 0.98:
        risks.append("mutation_gate_pass_rate_below_target")
    if signals["advisor_history_trend_needs_review"]:
        risks.append("policy_autotune_advisor_history_trend_needs_review")
    if signals["advisor_history_rollback_rate_high"]:
        risks.append("policy_autotune_advisor_rollback_rate_high")
    if signals["advisor_history_latest_action_rollback_review"]:
        risks.append("policy_autotune_advisor_latest_action_rollback_review")
    if signals["advisor_history_top_driver_recommended_component_dominant"]:
        risks.append("policy_autotune_advisor_top_driver_recommended_component_dominant")
    if signals["advisor_history_dominant_top_driver_changed"]:
        risks.append("policy_autotune_advisor_dominant_top_driver_changed")
    if signals["runtime_ledger_fail_rate_high"]:
        risks.append("runtime_ledger_fail_rate_high")
    if signals["runtime_ledger_needs_review_rate_high"]:
        risks.append("runtime_ledger_needs_review_rate_high")

    return {
        "status": status,
        "signals": signals,
        "kpis": {
            "strict_downgrade_rate": repair_compare.get("strict_downgrade_rate"),
            "downgrade_count": downgrade_count,
            "strategy_compare_relation": repair_compare.get("strategy_compare_relation"),
            "recommended_profile": recommended_profile,
            "review_recovery_rate": review_recovery_rate,
            "strict_non_pass_rate": strict_non_pass_rate,
            "approval_rate": kpis.get("approval_rate"),
            "fail_rate": kpis.get("fail_rate"),
            "invariant_repair_compare_status": invariant.get("status"),
            "invariant_repair_recommended_profile": invariant_best_profile,
            "invariant_repair_compare_relation": (
                "switched" if invariant_switch_recommended else "unchanged"
            ),
            "invariant_repair_top_score_margin": invariant.get("top_score_margin"),
            "mutation_latest_match_rate": mutation_match_rate,
            "mutation_latest_gate_pass_rate": mutation_gate_pass_rate,
            "mutation_trend_status": mutation_trend_status,
            "mutation_compare_decision": mutation_compare_decision,
            "policy_autotune_advisor_latest_action": advisor_history_latest_action,
            "policy_autotune_advisor_tighten_rate": advisor_history_tighten_rate,
            "policy_autotune_advisor_rollback_review_rate": advisor_history_rollback_rate,
            "policy_autotune_advisor_trend_status": advisor_history_trend_status,
            "policy_autotune_advisor_latest_top_driver": advisor_history_latest_top_driver,
            "policy_autotune_advisor_top_driver_non_null_rate": advisor_history_top_driver_non_null_rate,
            "runtime_ledger_total_records": runtime_ledger.get("total_records"),
            "runtime_ledger_pass_rate": runtime_ledger.get("pass_rate"),
            "runtime_ledger_fail_rate": runtime_ledger.get("fail_rate"),
            "runtime_ledger_needs_review_rate": runtime_ledger.get("needs_review_rate"),
        },
        "policy_profiles": {
            "compare_from": compare_from,
            "compare_to": repair_compare.get("to_policy_profile"),
            "recommended_profile": recommended_profile,
            "invariant_repair_compare_from": invariant_from_profile,
            "invariant_repair_recommended_profile": invariant_best_profile,
            "review_counts": review.get("policy_profile_counts", {}),
        },
        "sources": {
            "repair_batch_summary_path": repair.get("_source_path"),
            "review_ledger_summary_path": review.get("_source_path"),
            "ci_matrix_summary_path": matrix.get("_source_path"),
            "invariant_repair_compare_summary_path": invariant_compare.get("_source_path"),
            "mutation_dashboard_summary_path": mutation_dashboard.get("_source_path"),
            "policy_autotune_advisor_history_summary_path": policy_autotune_advisor_history.get("_source_path"),
            "runtime_ledger_summary_path": runtime_ledger_summary.get("_source_path"),
        },
        "risks": risks,
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    kpis = summary.get("kpis", {})
    lines = [
        "# GateForge Governance Snapshot",
        "",
        f"- status: `{summary.get('status')}`",
        f"- strict_downgrade_rate: `{kpis.get('strict_downgrade_rate')}`",
        f"- downgrade_count: `{kpis.get('downgrade_count')}`",
        f"- strategy_compare_relation: `{kpis.get('strategy_compare_relation')}`",
        f"- recommended_profile: `{kpis.get('recommended_profile')}`",
        f"- review_recovery_rate: `{kpis.get('review_recovery_rate')}`",
        f"- strict_non_pass_rate: `{kpis.get('strict_non_pass_rate')}`",
        f"- approval_rate: `{kpis.get('approval_rate')}`",
        f"- fail_rate: `{kpis.get('fail_rate')}`",
        f"- policy_autotune_advisor_latest_action: `{kpis.get('policy_autotune_advisor_latest_action')}`",
        f"- policy_autotune_advisor_tighten_rate: `{kpis.get('policy_autotune_advisor_tighten_rate')}`",
        f"- policy_autotune_advisor_rollback_review_rate: `{kpis.get('policy_autotune_advisor_rollback_review_rate')}`",
        f"- policy_autotune_advisor_trend_status: `{kpis.get('policy_autotune_advisor_trend_status')}`",
        f"- policy_autotune_advisor_latest_top_driver: `{kpis.get('policy_autotune_advisor_latest_top_driver')}`",
        f"- policy_autotune_advisor_top_driver_non_null_rate: `{kpis.get('policy_autotune_advisor_top_driver_non_null_rate')}`",
        f"- runtime_ledger_total_records: `{kpis.get('runtime_ledger_total_records')}`",
        f"- runtime_ledger_pass_rate: `{kpis.get('runtime_ledger_pass_rate')}`",
        f"- runtime_ledger_fail_rate: `{kpis.get('runtime_ledger_fail_rate')}`",
        f"- runtime_ledger_needs_review_rate: `{kpis.get('runtime_ledger_needs_review_rate')}`",
        "",
        "## Risks",
        "",
    ]
    risks = summary.get("risks", [])
    if risks:
        for r in risks:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Sources", ""])
    for k, v in summary.get("sources", {}).items():
        lines.append(f"- {k}: `{v}`")

    trend = summary.get("trend")
    if isinstance(trend, dict):
        lines.extend(
            [
                "",
                "## Trend vs Previous Snapshot",
                "",
                f"- status_transition: `{trend.get('status_transition')}`",
                "",
                "### New Risks",
                "",
            ]
        )
        new_risks = trend.get("new_risks", [])
        if new_risks:
            for r in new_risks:
                lines.append(f"- `{r}`")
        else:
            lines.append("- `none`")
        lines.extend(["", "### Resolved Risks", ""])
        resolved = trend.get("resolved_risks", [])
        if resolved:
            for r in resolved:
                lines.append(f"- `{r}`")
        else:
            lines.append("- `none`")
        lines.extend(["", "### KPI Delta", ""])
        delta = trend.get("kpi_delta", {})
        for k in sorted(delta.keys()):
            lines.append(f"- {k}: `{delta[k]}`")

    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a governance snapshot from repair/review/matrix summaries")
    parser.add_argument("--repair-batch-summary", default=None, help="Path to repair_batch summary JSON")
    parser.add_argument("--review-ledger-summary", default=None, help="Path to review_ledger summary JSON")
    parser.add_argument("--ci-matrix-summary", default=None, help="Path to ci matrix summary JSON")
    parser.add_argument(
        "--invariant-repair-compare-summary",
        default=None,
        help="Path to invariant_repair_compare summary JSON",
    )
    parser.add_argument(
        "--mutation-dashboard-summary",
        default=None,
        help="Path to mutation dashboard summary JSON",
    )
    parser.add_argument(
        "--policy-autotune-advisor-history-summary",
        default=None,
        help="Path to policy autotune advisor history demo summary JSON",
    )
    parser.add_argument(
        "--runtime-ledger-summary",
        default=None,
        help="Path to runtime decision ledger summary JSON",
    )
    parser.add_argument("--previous-summary", default=None, help="Optional previous governance snapshot JSON")
    parser.add_argument("--out", default="artifacts/governance_snapshot/summary.json", help="Output JSON path")
    parser.add_argument("--report", default=None, help="Output markdown path")
    args = parser.parse_args()

    repair = _load_json(args.repair_batch_summary)
    review = _load_json(args.review_ledger_summary)
    matrix = _load_json(args.ci_matrix_summary)
    invariant_compare = _load_json(args.invariant_repair_compare_summary)
    mutation_dashboard = _load_json(args.mutation_dashboard_summary)
    policy_autotune_advisor_history = _load_json(args.policy_autotune_advisor_history_summary)
    runtime_ledger_summary = _load_json(args.runtime_ledger_summary)
    if args.repair_batch_summary:
        repair["_source_path"] = args.repair_batch_summary
    if args.review_ledger_summary:
        review["_source_path"] = args.review_ledger_summary
    if args.ci_matrix_summary:
        matrix["_source_path"] = args.ci_matrix_summary
    if args.invariant_repair_compare_summary:
        invariant_compare["_source_path"] = args.invariant_repair_compare_summary
    if args.mutation_dashboard_summary:
        mutation_dashboard["_source_path"] = args.mutation_dashboard_summary
    if args.policy_autotune_advisor_history_summary:
        policy_autotune_advisor_history["_source_path"] = args.policy_autotune_advisor_history_summary
    if args.runtime_ledger_summary:
        runtime_ledger_summary["_source_path"] = args.runtime_ledger_summary

    summary = _compute_summary(
        repair,
        review,
        matrix,
        invariant_compare,
        mutation_dashboard,
        policy_autotune_advisor_history,
        runtime_ledger_summary,
    )
    if args.previous_summary:
        previous = _load_json(args.previous_summary)
        if previous:
            summary["trend"] = _compute_trend(summary, previous)
            summary["sources"]["previous_snapshot_path"] = args.previous_summary
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)

    print(json.dumps({"status": summary.get("status"), "risks": summary.get("risks", [])}))
    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
