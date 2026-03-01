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


def _to_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _round(value: float) -> float:
    return round(value, 2)


def _compute_metrics(
    evidence_pack: dict,
    registry: dict,
    backlog: dict,
    replay_eval: dict,
    milestone_checkpoint: dict,
    milestone_checkpoint_trend: dict,
    milestone_public_brief: dict,
    intake_summary: dict,
    previous_intake_summary: dict,
    intake_growth_execution_board: dict,
    intake_growth_execution_board_history: dict,
    intake_growth_execution_board_history_trend: dict,
    model_intake_board_history: dict,
    model_intake_board_history_trend: dict,
    anchor_model_pack_history: dict,
    anchor_model_pack_history_trend: dict,
    failure_matrix_expansion_history: dict,
    failure_matrix_expansion_history_trend: dict,
    model_asset_momentum: dict,
    model_asset_momentum_history: dict,
    model_asset_momentum_history_trend: dict,
    model_asset_target_gap: dict,
    model_asset_target_gap_history: dict,
    model_asset_target_gap_history_trend: dict,
) -> dict:
    evidence_strength = _to_float(evidence_pack.get("evidence_strength_score", 0.0))
    sections_present = _to_int(evidence_pack.get("evidence_sections_present", 0))

    total_records = _to_int(registry.get("total_records", 0))
    missing_scales = len(registry.get("missing_model_scales") or []) if isinstance(registry.get("missing_model_scales"), list) else 3
    scale_coverage_score = (3 - min(3, missing_scales)) * 10

    coverage_depth_index = _clamp((min(50, total_records * 2.0) + scale_coverage_score + min(20, sections_present * 2.0)))

    replay_score = _to_int(replay_eval.get("evaluation_score", 0))
    replay_status = str(replay_eval.get("status") or "")
    replay_status_bonus = 8 if replay_status == "PASS" else (2 if replay_status == "NEEDS_REVIEW" else -6)
    governance_effectiveness_index = _clamp((evidence_strength * 0.65) + ((replay_score + 5) * 3.5) + replay_status_bonus)

    p0_count = _to_int(((backlog.get("priority_counts") or {}).get("P0", 0)))
    open_tasks = _to_int(backlog.get("total_open_tasks", 0))
    replay_reco = str(replay_eval.get("recommendation") or "")
    reco_bonus = 10 if replay_reco == "ADOPT_PATCH" else (3 if replay_reco == "LIMITED_ROLLOUT" else -8)
    policy_learning_velocity = _clamp(55 - min(25, p0_count * 6) - min(10, int(open_tasks / 2)) + reco_bonus)

    checkpoint_score = _to_float(milestone_checkpoint.get("checkpoint_score", 50.0))
    checkpoint_decision = str(milestone_checkpoint.get("milestone_decision") or "")
    checkpoint_trend_status = str(milestone_checkpoint_trend.get("status") or "")
    checkpoint_transition = str(((milestone_checkpoint_trend.get("trend") or {}).get("status_transition")) or "")
    brief_status = str(milestone_public_brief.get("milestone_status") or "")

    decision_bonus = 0.0
    if checkpoint_decision == "GO":
        decision_bonus = 7.0
    elif checkpoint_decision == "LIMITED_GO":
        decision_bonus = 2.0
    elif checkpoint_decision == "HOLD":
        decision_bonus = -10.0

    trend_bonus = 0.0
    if checkpoint_trend_status == "PASS":
        trend_bonus = 4.0
    elif checkpoint_trend_status == "NEEDS_REVIEW":
        trend_bonus = -3.0
    elif checkpoint_trend_status == "FAIL":
        trend_bonus = -8.0

    brief_bonus = 0.0
    if brief_status == "PASS":
        brief_bonus = 4.0
    elif brief_status == "NEEDS_REVIEW":
        brief_bonus = -2.0
    elif brief_status == "FAIL":
        brief_bonus = -8.0

    transition_penalty = 0.0
    if checkpoint_transition in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        transition_penalty = -5.0

    milestone_readiness_index = _clamp(
        (checkpoint_score * 0.7) + 20.0 + decision_bonus + trend_bonus + brief_bonus + transition_penalty
    )

    current_accepted = _to_int(intake_summary.get("accepted_count", 0))
    previous_accepted = _to_int(previous_intake_summary.get("accepted_count", current_accepted))
    accepted_delta = current_accepted - previous_accepted
    current_large = _to_int(
        intake_summary.get(
            "accepted_large_count",
            ((intake_summary.get("accepted_scale_counts") or {}).get("large", 0))
            if isinstance(intake_summary.get("accepted_scale_counts"), dict)
            else 0,
        )
    )
    previous_large = _to_int(
        previous_intake_summary.get(
            "accepted_large_count",
            ((previous_intake_summary.get("accepted_scale_counts") or {}).get("large", current_large))
            if isinstance(previous_intake_summary.get("accepted_scale_counts"), dict)
            else current_large,
        )
    )
    large_delta = current_large - previous_large
    reject_rate_pct = _to_float(intake_summary.get("reject_rate_pct", 0.0))

    intake_growth_score = _clamp(60.0 + (accepted_delta * 6.0) + (large_delta * 10.0) - max(0.0, reject_rate_pct - 30.0) * 0.8)
    board_status = str(intake_growth_execution_board.get("status") or "")
    board_history_status = str(intake_growth_execution_board_history.get("status") or "")
    board_history_trend_status = str(intake_growth_execution_board_history_trend.get("status") or "")
    board_execution_score = _to_float(intake_growth_execution_board.get("execution_score", 0.0))
    board_critical_open_tasks = _to_int(intake_growth_execution_board.get("critical_open_tasks", 0))
    board_projected_weeks = _to_int(intake_growth_execution_board.get("projected_weeks_to_target", 0))
    board_history_avg_execution_score = _to_float(
        intake_growth_execution_board_history.get("avg_execution_score", 0.0)
    )
    board_history_critical_open_rate = _to_float(
        intake_growth_execution_board_history.get("critical_open_tasks_rate", 0.0)
    )

    execution_readiness_index = _clamp(
        45.0
        + (board_execution_score * 0.38)
        + (board_history_avg_execution_score * 0.2)
        - min(20.0, board_critical_open_tasks * 6.0)
        - min(15.0, board_projected_weeks * 4.0)
        - min(15.0, board_history_critical_open_rate * 30.0)
        + (6.0 if board_status == "PASS" else (1.0 if board_status == "NEEDS_REVIEW" else -8.0))
        + (5.0 if board_history_status == "PASS" else (1.0 if board_history_status == "NEEDS_REVIEW" else -6.0))
        + (
            4.0
            if board_history_trend_status == "PASS"
            else (0.0 if board_history_trend_status == "NEEDS_REVIEW" else -5.0)
        )
    )

    intake_board_avg = _to_float(model_intake_board_history.get("avg_board_score", 0.0))
    intake_board_blocked_rate = _to_float(model_intake_board_history.get("blocked_rate", 0.0))
    intake_board_ingested_rate = _to_float(model_intake_board_history.get("ingested_rate", 0.0))
    intake_board_status = str(model_intake_board_history.get("status") or "")
    intake_board_trend_status = str(model_intake_board_history_trend.get("status") or "")

    anchor_avg_quality = _to_float(anchor_model_pack_history.get("avg_pack_quality_score", 0.0))
    anchor_avg_large = _to_float(anchor_model_pack_history.get("avg_selected_large_cases", 0.0))
    anchor_avg_failure_types = _to_float(anchor_model_pack_history.get("avg_unique_failure_types", 0.0))
    anchor_status = str(anchor_model_pack_history.get("status") or "")
    anchor_trend_status = str(anchor_model_pack_history_trend.get("status") or "")

    model_asset_quality_index = _clamp(
        30.0
        + (intake_board_avg * 0.28)
        + (anchor_avg_quality * 0.32)
        + min(10.0, anchor_avg_large * 2.0)
        + min(10.0, anchor_avg_failure_types * 1.6)
        + min(12.0, intake_board_ingested_rate * 30.0)
        - min(15.0, intake_board_blocked_rate * 30.0)
        + (5.0 if intake_board_status == "PASS" else (1.0 if intake_board_status == "NEEDS_REVIEW" else -6.0))
        + (
            4.0
            if intake_board_trend_status == "PASS"
            else (0.0 if intake_board_trend_status == "NEEDS_REVIEW" else -5.0)
        )
        + (5.0 if anchor_status == "PASS" else (1.0 if anchor_status == "NEEDS_REVIEW" else -6.0))
        + (4.0 if anchor_trend_status == "PASS" else (0.0 if anchor_trend_status == "NEEDS_REVIEW" else -5.0))
    )

    expansion_avg_readiness = _to_float(failure_matrix_expansion_history.get("avg_expansion_readiness_score", 0.0))
    expansion_avg_uncovered = _to_float(failure_matrix_expansion_history.get("avg_high_risk_uncovered_cells", 0.0))
    expansion_avg_tasks = _to_float(failure_matrix_expansion_history.get("avg_planned_expansion_tasks", 0.0))
    expansion_status = str(failure_matrix_expansion_history.get("status") or "")
    expansion_trend_status = str(failure_matrix_expansion_history_trend.get("status") or "")

    expansion_execution_index = _clamp(
        38.0
        + (expansion_avg_readiness * 0.42)
        + min(12.0, expansion_avg_tasks * 1.8)
        - min(20.0, expansion_avg_uncovered * 12.0)
        + (5.0 if expansion_status == "PASS" else (1.0 if expansion_status == "NEEDS_REVIEW" else -7.0))
        + (
            4.0
            if expansion_trend_status == "PASS"
            else (0.0 if expansion_trend_status == "NEEDS_REVIEW" else -5.0)
        )
    )

    momentum_score = _to_float(model_asset_momentum.get("momentum_score", 0.0))
    momentum_history_avg = _to_float(model_asset_momentum_history.get("avg_momentum_score", 0.0))
    momentum_status = str(model_asset_momentum.get("status") or "")
    momentum_history_status = str(model_asset_momentum_history.get("status") or "")
    momentum_history_trend_status = str(model_asset_momentum_history_trend.get("status") or "")
    delta_total_models = _to_float(model_asset_momentum.get("delta_total_real_models", 0.0))
    delta_large_models = _to_float(model_asset_momentum.get("delta_large_models", 0.0))
    target_gap_score = _to_float(model_asset_target_gap.get("target_gap_score", 0.0))
    target_gap_critical = _to_float(model_asset_target_gap.get("critical_gap_count", 0.0))
    target_gap_status = str(model_asset_target_gap.get("status") or "")
    target_gap_history_avg = _to_float(model_asset_target_gap_history.get("avg_target_gap_score", 0.0))
    target_gap_history_critical_avg = _to_float(model_asset_target_gap_history.get("avg_critical_gap_count", 0.0))
    target_gap_history_status = str(model_asset_target_gap_history.get("status") or "")
    target_gap_history_trend_status = str(model_asset_target_gap_history_trend.get("status") or "")
    target_gap_pressure_index = _clamp(
        88.0
        - min(35.0, target_gap_score * 0.9)
        - min(30.0, target_gap_critical * 12.0)
        - min(20.0, target_gap_history_avg * 0.45)
        - min(15.0, target_gap_history_critical_avg * 10.0)
        + (4.0 if target_gap_status == "PASS" else (0.0 if target_gap_status == "NEEDS_REVIEW" else -8.0))
        + (
            3.0
            if target_gap_history_status == "PASS"
            else (0.0 if target_gap_history_status == "NEEDS_REVIEW" else -6.0)
        )
        + (
            3.0
            if target_gap_history_trend_status == "PASS"
            else (0.0 if target_gap_history_trend_status == "NEEDS_REVIEW" else -5.0)
        )
    )

    momentum_resilience_index = _clamp(
        26.0
        + (momentum_score * 0.42)
        + (momentum_history_avg * 0.28)
        + min(10.0, max(0.0, delta_total_models) * 3.0)
        + min(9.0, max(0.0, delta_large_models) * 4.0)
        + (5.0 if momentum_status == "PASS" else (1.0 if momentum_status == "NEEDS_REVIEW" else -8.0))
        + (4.0 if momentum_history_status == "PASS" else (1.0 if momentum_history_status == "NEEDS_REVIEW" else -6.0))
        + (
            4.0
            if momentum_history_trend_status == "PASS"
            else (0.0 if momentum_history_trend_status == "NEEDS_REVIEW" else -5.0)
        )
        + (target_gap_pressure_index * 0.18)
    )

    moat_score = _clamp(
        (coverage_depth_index * 0.23)
        + (governance_effectiveness_index * 0.23)
        + (policy_learning_velocity * 0.12)
        + (milestone_readiness_index * 0.10)
        + (intake_growth_score * 0.06)
        + (execution_readiness_index * 0.08)
        + (model_asset_quality_index * 0.08)
        + (expansion_execution_index * 0.06)
        + (momentum_resilience_index * 0.04)
        + (target_gap_pressure_index * 0.04)
    )

    return {
        "coverage_depth_index": _round(coverage_depth_index),
        "governance_effectiveness_index": _round(governance_effectiveness_index),
        "policy_learning_velocity": _round(policy_learning_velocity),
        "milestone_readiness_index": _round(milestone_readiness_index),
        "intake_growth_score": _round(intake_growth_score),
        "execution_readiness_index": _round(execution_readiness_index),
        "model_asset_quality_index": _round(model_asset_quality_index),
        "expansion_execution_index": _round(expansion_execution_index),
        "momentum_resilience_index": _round(momentum_resilience_index),
        "target_gap_pressure_index": _round(target_gap_pressure_index),
        "model_asset_target_gap_score": _round(target_gap_score),
        "model_asset_target_gap_critical_gap_count": _round(target_gap_critical),
        "intake_reject_rate_pct": _round(reject_rate_pct),
        "moat_score": _round(moat_score),
    }


def _compute_status(moat_score: float, evidence_status: str) -> str:
    if evidence_status == "FAIL":
        return "FAIL"
    if moat_score >= 70:
        return "PASS"
    return "NEEDS_REVIEW"


def _trend(current: dict, previous: dict) -> dict:
    prev_metrics = previous.get("metrics") if isinstance(previous.get("metrics"), dict) else {}
    curr_metrics = current.get("metrics") if isinstance(current.get("metrics"), dict) else {}

    def delta(key: str) -> float:
        return _round(_to_float(curr_metrics.get(key, 0.0)) - _to_float(prev_metrics.get(key, 0.0)))

    status_transition = f"{previous.get('status', 'UNKNOWN')}->{current.get('status', 'UNKNOWN')}"
    moat_delta = delta("moat_score")
    alerts: list[str] = []
    if moat_delta < -5:
        alerts.append("moat_score_drop_significant")
    if status_transition in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("status_worsened")

    return {
        "status_transition": status_transition,
        "delta": {
            "coverage_depth_index": delta("coverage_depth_index"),
            "governance_effectiveness_index": delta("governance_effectiveness_index"),
            "policy_learning_velocity": delta("policy_learning_velocity"),
            "milestone_readiness_index": delta("milestone_readiness_index"),
            "execution_readiness_index": delta("execution_readiness_index"),
            "model_asset_quality_index": delta("model_asset_quality_index"),
            "expansion_execution_index": delta("expansion_execution_index"),
            "momentum_resilience_index": delta("momentum_resilience_index"),
            "target_gap_pressure_index": delta("target_gap_pressure_index"),
            "moat_score": moat_delta,
        },
        "alerts": alerts,
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    trend = payload.get("trend") if isinstance(payload.get("trend"), dict) else {}
    lines = [
        "# GateForge Moat Trend Snapshot",
        "",
        f"- status: `{payload.get('status')}`",
        f"- moat_score: `{metrics.get('moat_score')}`",
        f"- coverage_depth_index: `{metrics.get('coverage_depth_index')}`",
        f"- governance_effectiveness_index: `{metrics.get('governance_effectiveness_index')}`",
        f"- policy_learning_velocity: `{metrics.get('policy_learning_velocity')}`",
        f"- milestone_readiness_index: `{metrics.get('milestone_readiness_index')}`",
        f"- intake_growth_score: `{metrics.get('intake_growth_score')}`",
        f"- execution_readiness_index: `{metrics.get('execution_readiness_index')}`",
        f"- model_asset_quality_index: `{metrics.get('model_asset_quality_index')}`",
        f"- expansion_execution_index: `{metrics.get('expansion_execution_index')}`",
        f"- momentum_resilience_index: `{metrics.get('momentum_resilience_index')}`",
        f"- target_gap_pressure_index: `{metrics.get('target_gap_pressure_index')}`",
        f"- model_asset_target_gap_score: `{metrics.get('model_asset_target_gap_score')}`",
        f"- model_asset_target_gap_critical_gap_count: `{metrics.get('model_asset_target_gap_critical_gap_count')}`",
        f"- intake_reject_rate_pct: `{metrics.get('intake_reject_rate_pct')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        f"- moat_score_delta: `{(trend.get('delta') or {}).get('moat_score')}`",
        "",
        "## Trend Alerts",
        "",
    ]
    alerts = trend.get("alerts") if isinstance(trend.get("alerts"), list) else []
    if alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build moat trend snapshot from governance evidence signals")
    parser.add_argument("--evidence-pack", required=True)
    parser.add_argument("--failure-corpus-registry-summary", default=None)
    parser.add_argument("--blind-spot-backlog", default=None)
    parser.add_argument("--policy-patch-replay-evaluator", default=None)
    parser.add_argument("--milestone-checkpoint-summary", default=None)
    parser.add_argument("--milestone-checkpoint-trend-summary", default=None)
    parser.add_argument("--milestone-public-brief-summary", default=None)
    parser.add_argument("--real-model-intake-summary", default=None)
    parser.add_argument("--previous-real-model-intake-summary", default=None)
    parser.add_argument("--intake-growth-execution-board-summary", default=None)
    parser.add_argument("--intake-growth-execution-board-history-summary", default=None)
    parser.add_argument("--intake-growth-execution-board-history-trend-summary", default=None)
    parser.add_argument("--model-intake-board-history-summary", default=None)
    parser.add_argument("--model-intake-board-history-trend-summary", default=None)
    parser.add_argument("--anchor-model-pack-history-summary", default=None)
    parser.add_argument("--anchor-model-pack-history-trend-summary", default=None)
    parser.add_argument("--failure-matrix-expansion-history-summary", default=None)
    parser.add_argument("--failure-matrix-expansion-history-trend-summary", default=None)
    parser.add_argument("--model-asset-momentum-summary", default=None)
    parser.add_argument("--model-asset-momentum-history-summary", default=None)
    parser.add_argument("--model-asset-momentum-history-trend-summary", default=None)
    parser.add_argument("--model-asset-target-gap-summary", default=None)
    parser.add_argument("--model-asset-target-gap-history-summary", default=None)
    parser.add_argument("--model-asset-target-gap-history-trend-summary", default=None)
    parser.add_argument("--previous-snapshot", default=None)
    parser.add_argument("--out", default="artifacts/dataset_moat_trend_snapshot/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    evidence_pack = _load_json(args.evidence_pack)
    registry = _load_json(args.failure_corpus_registry_summary)
    backlog = _load_json(args.blind_spot_backlog)
    replay_eval = _load_json(args.policy_patch_replay_evaluator)
    milestone_checkpoint = _load_json(args.milestone_checkpoint_summary)
    milestone_checkpoint_trend = _load_json(args.milestone_checkpoint_trend_summary)
    milestone_public_brief = _load_json(args.milestone_public_brief_summary)
    intake_summary = _load_json(args.real_model_intake_summary)
    previous_intake_summary = _load_json(args.previous_real_model_intake_summary)
    intake_growth_execution_board = _load_json(args.intake_growth_execution_board_summary)
    intake_growth_execution_board_history = _load_json(args.intake_growth_execution_board_history_summary)
    intake_growth_execution_board_history_trend = _load_json(args.intake_growth_execution_board_history_trend_summary)
    model_intake_board_history = _load_json(args.model_intake_board_history_summary)
    model_intake_board_history_trend = _load_json(args.model_intake_board_history_trend_summary)
    anchor_model_pack_history = _load_json(args.anchor_model_pack_history_summary)
    anchor_model_pack_history_trend = _load_json(args.anchor_model_pack_history_trend_summary)
    failure_matrix_expansion_history = _load_json(args.failure_matrix_expansion_history_summary)
    failure_matrix_expansion_history_trend = _load_json(args.failure_matrix_expansion_history_trend_summary)
    model_asset_momentum = _load_json(args.model_asset_momentum_summary)
    model_asset_momentum_history = _load_json(args.model_asset_momentum_history_summary)
    model_asset_momentum_history_trend = _load_json(args.model_asset_momentum_history_trend_summary)
    model_asset_target_gap = _load_json(args.model_asset_target_gap_summary)
    model_asset_target_gap_history = _load_json(args.model_asset_target_gap_history_summary)
    model_asset_target_gap_history_trend = _load_json(args.model_asset_target_gap_history_trend_summary)
    previous = _load_json(args.previous_snapshot)

    metrics = _compute_metrics(
        evidence_pack,
        registry,
        backlog,
        replay_eval,
        milestone_checkpoint,
        milestone_checkpoint_trend,
        milestone_public_brief,
        intake_summary,
        previous_intake_summary,
        intake_growth_execution_board,
        intake_growth_execution_board_history,
        intake_growth_execution_board_history_trend,
        model_intake_board_history,
        model_intake_board_history_trend,
        anchor_model_pack_history,
        anchor_model_pack_history_trend,
        failure_matrix_expansion_history,
        failure_matrix_expansion_history_trend,
        model_asset_momentum,
        model_asset_momentum_history,
        model_asset_momentum_history_trend,
        model_asset_target_gap,
        model_asset_target_gap_history,
        model_asset_target_gap_history_trend,
    )
    status = _compute_status(_to_float(metrics.get("moat_score", 0.0)), str(evidence_pack.get("status") or ""))

    current_accepted = _to_int(intake_summary.get("accepted_count", 0))
    previous_accepted = _to_int(previous_intake_summary.get("accepted_count", current_accepted))
    current_large = _to_int(
        intake_summary.get(
            "accepted_large_count",
            ((intake_summary.get("accepted_scale_counts") or {}).get("large", 0))
            if isinstance(intake_summary.get("accepted_scale_counts"), dict)
            else 0,
        )
    )
    previous_large = _to_int(
        previous_intake_summary.get(
            "accepted_large_count",
            ((previous_intake_summary.get("accepted_scale_counts") or {}).get("large", current_large))
            if isinstance(previous_intake_summary.get("accepted_scale_counts"), dict)
            else current_large,
        )
    )
    intake_growth = {
        "accepted_count": current_accepted,
        "accepted_large_count": current_large,
        "reject_rate_pct": _round(_to_float(intake_summary.get("reject_rate_pct", 0.0))),
        "accepted_count_delta": current_accepted - previous_accepted,
        "accepted_large_delta": current_large - previous_large,
    }

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "metrics": metrics,
        "intake_growth": intake_growth,
        "sources": {
            "evidence_pack": args.evidence_pack,
            "failure_corpus_registry_summary": args.failure_corpus_registry_summary,
            "blind_spot_backlog": args.blind_spot_backlog,
            "policy_patch_replay_evaluator": args.policy_patch_replay_evaluator,
            "real_model_intake_summary": args.real_model_intake_summary,
            "previous_real_model_intake_summary": args.previous_real_model_intake_summary,
            "intake_growth_execution_board_summary": args.intake_growth_execution_board_summary,
            "intake_growth_execution_board_history_summary": args.intake_growth_execution_board_history_summary,
            "intake_growth_execution_board_history_trend_summary": args.intake_growth_execution_board_history_trend_summary,
            "model_intake_board_history_summary": args.model_intake_board_history_summary,
            "model_intake_board_history_trend_summary": args.model_intake_board_history_trend_summary,
            "anchor_model_pack_history_summary": args.anchor_model_pack_history_summary,
            "anchor_model_pack_history_trend_summary": args.anchor_model_pack_history_trend_summary,
            "failure_matrix_expansion_history_summary": args.failure_matrix_expansion_history_summary,
            "failure_matrix_expansion_history_trend_summary": args.failure_matrix_expansion_history_trend_summary,
            "model_asset_momentum_summary": args.model_asset_momentum_summary,
            "model_asset_momentum_history_summary": args.model_asset_momentum_history_summary,
            "model_asset_momentum_history_trend_summary": args.model_asset_momentum_history_trend_summary,
            "model_asset_target_gap_summary": args.model_asset_target_gap_summary,
            "model_asset_target_gap_history_summary": args.model_asset_target_gap_history_summary,
            "model_asset_target_gap_history_trend_summary": args.model_asset_target_gap_history_trend_summary,
            "milestone_checkpoint_summary": args.milestone_checkpoint_summary,
            "milestone_checkpoint_trend_summary": args.milestone_checkpoint_trend_summary,
            "milestone_public_brief_summary": args.milestone_public_brief_summary,
            "previous_snapshot": args.previous_snapshot,
        },
    }
    summary["trend"] = _trend(summary, previous if previous else {"status": status, "metrics": metrics})

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "moat_score": metrics.get("moat_score")}))
    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
