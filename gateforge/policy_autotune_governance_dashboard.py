from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Policy Auto-Tune Governance Dashboard",
        "",
        f"- bundle_status: `{payload.get('bundle_status')}`",
        f"- latest_effectiveness_decision: `{payload.get('latest_effectiveness_decision')}`",
        f"- improvement_rate: `{payload.get('improvement_rate')}`",
        f"- regression_rate: `{payload.get('regression_rate')}`",
        f"- quality_regressed_rate: `{payload.get('quality_regressed_rate')}`",
        f"- trend_status: `{payload.get('trend_status')}`",
        f"- trend_alerts_count: `{payload.get('trend_alerts_count')}`",
        f"- tuned_top_score_margin: `{payload.get('tuned_top_score_margin')}`",
        f"- tuned_explanation_completeness: `{payload.get('tuned_explanation_completeness')}`",
        f"- tuned_pairwise_net_margin: `{payload.get('tuned_pairwise_net_margin')}`",
        f"- tuned_leader_profile: `{payload.get('tuned_leader_profile')}`",
        f"- tuned_leader_pairwise_win_count: `{payload.get('tuned_leader_pairwise_win_count')}`",
        f"- tuned_leader_pairwise_loss_count: `{payload.get('tuned_leader_pairwise_loss_count')}`",
        f"- tuned_leader_total_score: `{payload.get('tuned_leader_total_score')}`",
        f"- tuned_runner_up_score_gap_to_best: `{payload.get('tuned_runner_up_score_gap_to_best')}`",
        f"- advisor_history_latest_action: `{payload.get('advisor_history_latest_action')}`",
        f"- advisor_history_latest_top_driver: `{payload.get('advisor_history_latest_top_driver')}`",
        f"- advisor_history_top_driver_non_null_rate: `{payload.get('advisor_history_top_driver_non_null_rate')}`",
        f"- advisor_history_trend_status: `{payload.get('advisor_history_trend_status')}`",
        f"- advisor_history_trend_alerts_count: `{payload.get('advisor_history_trend_alerts_count')}`",
        f"- advisor_history_dominant_top_driver_current: `{payload.get('advisor_history_dominant_top_driver_current')}`",
        "",
        "## Advisor Top Driver Distribution",
        "",
    ]
    distribution = payload.get("advisor_history_top_driver_distribution", {})
    if isinstance(distribution, dict) and distribution:
        for key in sorted(distribution.keys()):
            lines.append(f"- `{key}`: `{distribution.get(key)}`")
    else:
        lines.append("- `none`")
    lines.extend(
        [
            "",
        "## Result Flags",
        "",
        ]
    )
    flags = payload.get("result_flags", {})
    if isinstance(flags, dict):
        for k in sorted(flags):
            lines.append(f"- {k}: `{flags[k]}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate policy autotune governance artifacts into dashboard")
    parser.add_argument("--flow-summary", default="artifacts/policy_autotune_governance_demo/flow_summary.json")
    parser.add_argument("--effectiveness", default="artifacts/policy_autotune_governance_demo/effectiveness.json")
    parser.add_argument("--history", default="artifacts/policy_autotune_governance_history_demo/summary.json")
    parser.add_argument("--trend", default="artifacts/policy_autotune_governance_history_demo/trend.json")
    parser.add_argument("--advisor-history-summary", default=None)
    parser.add_argument("--advisor-history-trend", default=None)
    parser.add_argument("--out", default="artifacts/policy_autotune_governance_history_demo/dashboard.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    flow = _load_json(args.flow_summary)
    eff = _load_json(args.effectiveness)
    history = _load_json(args.history)
    trend = _load_json(args.trend)
    advisor_history = _load_json(args.advisor_history_summary)
    advisor_history_trend = _load_json(args.advisor_history_trend)
    baseline_compare = _load_json(str((flow.get("baseline") or {}).get("compare_path") or ""))
    tuned_compare = _load_json(str((flow.get("tuned") or {}).get("compare_path") or ""))
    tuned_leaderboard = tuned_compare.get("decision_explanation_leaderboard")
    tuned_pairwise_net_margin = None
    tuned_leader_profile = None
    tuned_leader_pairwise_win_count = None
    tuned_leader_pairwise_loss_count = None
    tuned_leader_total_score = None
    tuned_runner_up_score_gap_to_best = None
    if isinstance(tuned_leaderboard, list) and tuned_leaderboard and isinstance(tuned_leaderboard[0], dict):
        leader = tuned_leaderboard[0]
        tuned_pairwise_net_margin = leader.get("pairwise_net_margin")
        tuned_leader_profile = leader.get("profile")
        tuned_leader_pairwise_win_count = leader.get("pairwise_win_count")
        tuned_leader_pairwise_loss_count = leader.get("pairwise_loss_count")
        tuned_leader_total_score = leader.get("total_score")
    if isinstance(tuned_leaderboard, list) and len(tuned_leaderboard) >= 2 and isinstance(tuned_leaderboard[1], dict):
        tuned_runner_up_score_gap_to_best = tuned_leaderboard[1].get("score_gap_to_best")

    trend_payload = trend.get("trend") if isinstance(trend.get("trend"), dict) else {}
    advisor_history_trend_payload = (
        advisor_history_trend.get("trend") if isinstance(advisor_history_trend.get("trend"), dict) else {}
    )

    flags = {
        "flow_summary_present": "PASS" if isinstance(flow.get("advisor_profile"), str) else "FAIL",
        "effectiveness_present": "PASS" if eff.get("decision") in {"IMPROVED", "UNCHANGED", "REGRESSED"} else "FAIL",
        "history_present": "PASS" if isinstance(history.get("total_records"), int) else "FAIL",
        "trend_present": "PASS" if trend.get("status") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
        "advisor_history_present": "PASS"
        if (args.advisor_history_summary is None or isinstance(advisor_history.get("total_records"), int))
        else "FAIL",
        "advisor_history_trend_present": "PASS"
        if (args.advisor_history_trend is None or advisor_history_trend.get("status") in {"PASS", "NEEDS_REVIEW"})
        else "FAIL",
    }
    bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bundle_status": bundle_status,
        "advisor_profile": flow.get("advisor_profile"),
        "latest_effectiveness_decision": eff.get("decision"),
        "delta_apply_score": eff.get("delta_apply_score"),
        "delta_compare_score": eff.get("delta_compare_score"),
        "improvement_rate": history.get("improvement_rate"),
        "regression_rate": history.get("regression_rate"),
        "quality_regressed_rate": history.get("quality_regressed_rate"),
        "history_alerts": history.get("alerts", []),
        "trend_status": trend.get("status"),
        "trend_alerts": trend_payload.get("alerts", []),
        "trend_alerts_count": len(trend_payload.get("alerts", []) or []),
        "advisor_history_latest_action": advisor_history.get("latest_action"),
        "advisor_history_latest_top_driver": advisor_history.get("latest_top_driver"),
        "advisor_history_top_driver_non_null_rate": advisor_history.get("top_driver_non_null_rate"),
        "advisor_history_top_driver_distribution": advisor_history.get("top_driver_distribution", {}),
        "advisor_history_trend_status": advisor_history_trend.get("status"),
        "advisor_history_trend_alerts": advisor_history_trend_payload.get("alerts", []),
        "advisor_history_trend_alerts_count": len(advisor_history_trend_payload.get("alerts", []) or []),
        "advisor_history_dominant_top_driver_current": advisor_history_trend_payload.get(
            "dominant_top_driver_current"
        ),
        "baseline_top_score_margin": baseline_compare.get("top_score_margin"),
        "baseline_explanation_completeness": baseline_compare.get("explanation_completeness"),
        "tuned_top_score_margin": tuned_compare.get("top_score_margin"),
        "tuned_explanation_completeness": tuned_compare.get("explanation_completeness"),
        "tuned_pairwise_net_margin": tuned_pairwise_net_margin,
        "tuned_leader_profile": tuned_leader_profile,
        "tuned_leader_pairwise_win_count": tuned_leader_pairwise_win_count,
        "tuned_leader_pairwise_loss_count": tuned_leader_pairwise_loss_count,
        "tuned_leader_total_score": tuned_leader_total_score,
        "tuned_runner_up_score_gap_to_best": tuned_runner_up_score_gap_to_best,
        "paths": {
            "flow_summary": args.flow_summary,
            "effectiveness": args.effectiveness,
            "history": args.history,
            "trend": args.trend,
            "advisor_history_summary": args.advisor_history_summary,
            "advisor_history_trend": args.advisor_history_trend,
        },
        "result_flags": flags,
    }
    payload["result_flags"]["tuned_compare_explanation_present"] = (
        "PASS"
        if isinstance(payload.get("tuned_top_score_margin"), int)
        and isinstance(payload.get("tuned_explanation_completeness"), int)
        else "FAIL"
    )
    payload["result_flags"]["tuned_pairwise_signal_present"] = (
        "PASS" if isinstance(payload.get("tuned_pairwise_net_margin"), int) else "FAIL"
    )
    payload["result_flags"]["tuned_leaderboard_present"] = (
        "PASS"
        if isinstance(payload.get("tuned_leader_profile"), str)
        and isinstance(payload.get("tuned_runner_up_score_gap_to_best"), int)
        else "FAIL"
    )
    final_bundle_status = "PASS" if all(v == "PASS" for v in payload["result_flags"].values()) else "FAIL"
    payload["bundle_status"] = final_bundle_status
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"bundle_status": final_bundle_status, "latest_effectiveness_decision": eff.get("decision")}))
    if final_bundle_status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
