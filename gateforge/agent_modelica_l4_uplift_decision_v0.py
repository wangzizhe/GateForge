from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "agent_modelica_l4_uplift_decision_v0"
PRIMARY_REASON_PRIORITY = [
    "infra",
    "missing_artifacts",
    "baseline_too_weak",
    "absolute_success_below_threshold",
    "quality_regression",
]


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


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
        "# Agent Modelica L4 Uplift Decision v0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- decision: `{payload.get('decision')}`",
        f"- primary_reason: `{payload.get('primary_reason')}`",
        f"- acceptance_mode: `{payload.get('acceptance_mode')}`",
        f"- main_success_at_k_pct: `{payload.get('main_success_at_k_pct')}`",
        f"- absolute_success_target_pct: `{payload.get('absolute_success_target_pct')}`",
        f"- main_delta_success_at_k_pp: `{payload.get('main_delta_success_at_k_pp')}`",
        f"- non_regression_ok: `{payload.get('non_regression_ok')}`",
        f"- main_infra_failure_count: `{payload.get('main_infra_failure_count')}`",
        f"- baseline_off_success_at_k_pct: `{payload.get('baseline_off_success_at_k_pct')}`",
        f"- baseline_meets_minimum: `{payload.get('baseline_meets_minimum')}`",
        f"- baseline_has_headroom: `{payload.get('baseline_has_headroom')}`",
        f"- baseline_headroom_max_pct: `{payload.get('baseline_headroom_max_pct')}`",
        f"- baseline_in_target_range: `{payload.get('baseline_in_target_range')}`",
        f"- consistency_ok: `{payload.get('consistency_ok')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _to_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _normalize_gate(value: object) -> str:
    text = str(value or "").strip().upper()
    if text in {"PASS", "FAIL", "NEEDS_REVIEW"}:
        return text
    return "UNKNOWN"


def _normalize_weekly(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in {"promote", "hold"}:
        return text
    return ""


def _normalize_acceptance_mode(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in {"delta_uplift", "absolute_non_regression"}:
        return text
    return "delta_uplift"


def _extract_compare_metrics(payload: dict) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "source_kind": "missing",
            "status": "UNKNOWN",
            "recommended_profile": "",
            "delta_success_at_k_pp": 0.0,
            "delta_regression_fail_rate_pp": 0.0,
            "delta_physics_fail_rate_pp": 0.0,
            "infra_failure_count_on": 0,
            "no_progress_rate_pct_on": 0.0,
            "llm_fallback_rate_pct_on": 0.0,
            "l4_primary_reason_on": "none",
            "reason_distribution_on": {},
            "on": {},
            "off": {},
        }

    if isinstance(payload.get("delta"), dict) and isinstance(payload.get("on"), dict):
        delta = payload.get("delta") if isinstance(payload.get("delta"), dict) else {}
        on = payload.get("on") if isinstance(payload.get("on"), dict) else {}
        off = payload.get("off") if isinstance(payload.get("off"), dict) else {}
        return {
            "source_kind": "ab_compare",
            "status": str(payload.get("status") or "UNKNOWN"),
            "recommended_profile": str(payload.get("policy_profile") or ""),
            "delta_success_at_k_pp": _to_float(delta.get("success_at_k_pp"), 0.0),
            "delta_regression_fail_rate_pp": _to_float(delta.get("regression_fail_rate_pp"), 0.0),
            "delta_physics_fail_rate_pp": _to_float(delta.get("physics_fail_rate_pp"), 0.0),
            "infra_failure_count_on": _to_int(on.get("infra_failure_count"), 0),
            "no_progress_rate_pct_on": _to_float(on.get("no_progress_rate_pct"), 0.0),
            "llm_fallback_rate_pct_on": _to_float(on.get("llm_fallback_rate_pct"), 0.0),
            "l4_primary_reason_on": str(on.get("l4_primary_reason") or "none"),
            "reason_distribution_on": on.get("reason_distribution") if isinstance(on.get("reason_distribution"), dict) else {},
            "on": on,
            "off": off,
        }

    best = payload.get("recommended_profile_result") if isinstance(payload.get("recommended_profile_result"), dict) else {}
    if not best:
        rows = payload.get("profile_results") if isinstance(payload.get("profile_results"), list) else []
        pass_rows = [x for x in rows if isinstance(x, dict) and str(x.get("status") or "") == "PASS"]
        if pass_rows:
            best = sorted(
                pass_rows,
                key=lambda x: (
                    -_to_float(x.get("delta_success_at_k_pp"), 0.0),
                    -_to_float(x.get("success_at_k_pct_on"), 0.0),
                    _to_float(x.get("no_progress_rate_pct_on"), 0.0),
                    _to_float(x.get("llm_fallback_rate_pct_on"), 0.0),
                    str(x.get("profile") or ""),
                ),
            )[0]
    if best:
        reason_dist = best.get("reason_distribution_on")
        if not isinstance(reason_dist, dict):
            reason_dist = {}
        on = {
            "success_at_k_pct": _to_float(best.get("success_at_k_pct_on"), 0.0),
            "infra_failure_count": _to_int(best.get("infra_failure_count_on"), 0),
            "no_progress_rate_pct": _to_float(best.get("no_progress_rate_pct_on"), 0.0),
            "llm_fallback_rate_pct": _to_float(best.get("llm_fallback_rate_pct_on"), 0.0),
            "l4_primary_reason": str(best.get("l4_primary_reason_on") or "none"),
            "reason_distribution": reason_dist,
        }
        off = {
            "success_at_k_pct": _to_float(best.get("success_at_k_pct_off"), 0.0),
        }
        return {
            "source_kind": "profile_sweep",
            "status": str(payload.get("status") or "UNKNOWN"),
            "recommended_profile": str(best.get("profile") or payload.get("recommended_profile") or ""),
            "delta_success_at_k_pp": _to_float(best.get("delta_success_at_k_pp"), 0.0),
            "delta_regression_fail_rate_pp": _to_float(best.get("delta_regression_fail_rate_pp"), 0.0),
            "delta_physics_fail_rate_pp": _to_float(best.get("delta_physics_fail_rate_pp"), 0.0),
            "infra_failure_count_on": _to_int(best.get("infra_failure_count_on"), 0),
            "no_progress_rate_pct_on": _to_float(best.get("no_progress_rate_pct_on"), 0.0),
            "llm_fallback_rate_pct_on": _to_float(best.get("llm_fallback_rate_pct_on"), 0.0),
            "l4_primary_reason_on": str(best.get("l4_primary_reason_on") or "none"),
            "reason_distribution_on": reason_dist,
            "on": on,
            "off": off,
        }

    return {
        "source_kind": "missing",
        "status": str(payload.get("status") or "UNKNOWN"),
        "recommended_profile": str(payload.get("recommended_profile") or ""),
        "delta_success_at_k_pp": 0.0,
        "delta_regression_fail_rate_pp": 0.0,
        "delta_physics_fail_rate_pp": 0.0,
        "infra_failure_count_on": 0,
        "no_progress_rate_pct_on": 0.0,
        "llm_fallback_rate_pct_on": 0.0,
        "l4_primary_reason_on": "none",
        "reason_distribution_on": {},
        "on": {},
        "off": {},
    }


def evaluate_l4_uplift_decision_v0(
    *,
    challenge_summary: dict,
    main_sweep_summary: dict,
    main_l5_summary: dict,
    main_weekly_summary: dict,
    night_sweep_summary: dict,
    night_l5_summary: dict,
    night_weekly_summary: dict,
    min_delta_success_pp: float = 5.0,
    absolute_success_target_pct: float = 85.0,
    non_regression_tolerance_pp: float = 0.0,
    max_regression_worsen_pp: float = 2.0,
    max_physics_worsen_pp: float = 2.0,
) -> dict:
    reasons: list[str] = []
    decision = "hold"
    status = "PASS"

    compare_main = _extract_compare_metrics(main_sweep_summary if isinstance(main_sweep_summary, dict) else {})
    compare_night = _extract_compare_metrics(night_sweep_summary if isinstance(night_sweep_summary, dict) else {})

    baseline_off_success = _to_float(challenge_summary.get("baseline_off_success_at_k_pct"), 0.0)
    baseline_meets_minimum = challenge_summary.get("baseline_meets_minimum")
    if baseline_meets_minimum is None:
        baseline_meets_minimum = challenge_summary.get("baseline_in_target_range")
    baseline_meets_minimum = baseline_meets_minimum is True
    baseline_headroom_max_pct = max(0.0, 100.0 - float(min_delta_success_pp))
    baseline_has_headroom = challenge_summary.get("baseline_has_headroom")
    if baseline_has_headroom is None:
        baseline_has_headroom = baseline_off_success <= baseline_headroom_max_pct
    baseline_has_headroom = baseline_has_headroom is True
    baseline_uplift_eligible = baseline_meets_minimum and baseline_has_headroom
    acceptance_mode = "absolute_non_regression" if baseline_meets_minimum and not baseline_has_headroom else "delta_uplift"
    if not baseline_meets_minimum:
        reasons.append("baseline_too_weak")

    missing_labels: list[str] = []
    if baseline_meets_minimum:
        required_payloads = (
            ("main_sweep_summary", main_sweep_summary),
            ("main_l5_summary", main_l5_summary),
            ("main_weekly_summary", main_weekly_summary),
            ("night_sweep_summary", night_sweep_summary),
            ("night_l5_summary", night_l5_summary),
            ("night_weekly_summary", night_weekly_summary),
        )
        for label, payload in required_payloads:
            if not isinstance(payload, dict) or not payload:
                missing_labels.append(label)
        if missing_labels:
            reasons.append("missing_artifacts")

    main_delta = _to_float(compare_main.get("delta_success_at_k_pp"), 0.0)
    main_delta_reg = _to_float(compare_main.get("delta_regression_fail_rate_pp"), 0.0)
    main_delta_phy = _to_float(compare_main.get("delta_physics_fail_rate_pp"), 0.0)
    main_success = _to_float(main_l5_summary.get("success_at_k_pct"), _to_float((compare_main.get("on") or {}).get("success_at_k_pct"), 0.0))
    non_regression_ok = main_l5_summary.get("non_regression_ok")
    if non_regression_ok is None:
        non_regression_ok = main_success >= (baseline_off_success - float(non_regression_tolerance_pp))
    non_regression_ok = non_regression_ok is True

    infra_main = _to_int(main_l5_summary.get("infra_failure_count"), _to_int(compare_main.get("infra_failure_count_on"), 0))
    infra_night = _to_int(night_l5_summary.get("infra_failure_count"), _to_int(compare_night.get("infra_failure_count_on"), 0))
    infra_total = infra_main + infra_night
    if infra_total > 0:
        reasons.append("infra")

    main_gate = _normalize_gate(main_l5_summary.get("gate_result") or main_l5_summary.get("status"))
    if baseline_meets_minimum and "missing_artifacts" not in reasons and "infra" not in reasons:
        if acceptance_mode == "absolute_non_regression":
            if main_success < float(absolute_success_target_pct):
                reasons.append("absolute_success_below_threshold")
        if (
            not non_regression_ok
            or main_delta_reg > float(max_regression_worsen_pp)
            or main_delta_phy > float(max_physics_worsen_pp)
            or (acceptance_mode == "delta_uplift" and main_delta < float(min_delta_success_pp))
            or main_gate != "PASS"
        ):
            reasons.append("quality_regression")

    main_weekly_rec = _normalize_weekly(main_weekly_summary.get("recommendation"))
    main_weekly_reason = str(main_weekly_summary.get("recommendation_reason") or "").strip()
    l4_main_reason = str(main_l5_summary.get("l4_primary_reason") or compare_main.get("l4_primary_reason_on") or "none")
    l4_main_reason = str(l4_main_reason or "none")

    consistency_reasons: list[str] = []
    if main_gate == "PASS" and main_weekly_rec == "promote":
        pass
    elif main_gate == "PASS" and main_weekly_rec == "hold":
        if main_weekly_reason not in {
            "insufficient_history",
            "insufficient_consecutive_history",
            "threshold_not_met",
            "two_week_consecutive_pass",
        }:
            consistency_reasons.append("main_gate_pass_weekly_hold_unexpected_reason")
    elif main_gate == "FAIL" and main_weekly_rec == "promote":
        consistency_reasons.append("main_gate_fail_weekly_promote_conflict")

    if main_weekly_reason and l4_main_reason and l4_main_reason not in {"none", "hard_checks_pass"}:
        if main_weekly_reason not in {l4_main_reason, "insufficient_consecutive_history", "insufficient_history"}:
            consistency_reasons.append("l4_reason_weekly_reason_mismatch")

    consistency_ok = len(consistency_reasons) == 0
    if not consistency_ok:
        status = "NEEDS_REVIEW"
    if "missing_artifacts" in reasons:
        status = "NEEDS_REVIEW"

    primary_reason = "none"
    for reason in PRIMARY_REASON_PRIORITY:
        if reason in reasons:
            primary_reason = reason
            break

    if not reasons:
        decision = "promote"
    else:
        decision = "hold"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision": decision,
        "primary_reason": primary_reason,
        "reason_priority": PRIMARY_REASON_PRIORITY,
        "reasons": sorted(set(reasons)),
        "acceptance_mode": acceptance_mode,
        "consistency_ok": consistency_ok,
        "consistency_reasons": consistency_reasons,
        "missing_artifact_labels": missing_labels,
        "main_success_at_k_pct": main_success,
        "absolute_success_target_pct": float(absolute_success_target_pct),
        "main_delta_success_at_k_pp": main_delta,
        "main_delta_regression_fail_rate_pp": main_delta_reg,
        "main_delta_physics_fail_rate_pp": main_delta_phy,
        "non_regression_tolerance_pp": float(non_regression_tolerance_pp),
        "non_regression_ok": non_regression_ok,
        "main_infra_failure_count": infra_main,
        "night_infra_failure_count": infra_night,
        "infra_failure_count_total": infra_total,
        "baseline_off_success_at_k_pct": baseline_off_success,
        "baseline_meets_minimum": baseline_meets_minimum,
        "baseline_has_headroom": baseline_has_headroom,
        "baseline_headroom_max_pct": baseline_headroom_max_pct,
        "baseline_eligible_for_uplift": baseline_uplift_eligible,
        "baseline_in_target_range": baseline_meets_minimum,
        "main_recommended_profile": str(compare_main.get("recommended_profile") or main_sweep_summary.get("recommended_profile") or ""),
        "main_no_progress_rate_pct": _to_float(compare_main.get("no_progress_rate_pct_on"), 0.0),
        "main_llm_fallback_rate_pct": _to_float(compare_main.get("llm_fallback_rate_pct_on"), 0.0),
        "main_reason_distribution": compare_main.get("reason_distribution_on") if isinstance(compare_main.get("reason_distribution_on"), dict) else {},
        "night_no_progress_rate_pct": _to_float(compare_night.get("no_progress_rate_pct_on"), 0.0),
        "night_llm_fallback_rate_pct": _to_float(compare_night.get("llm_fallback_rate_pct_on"), 0.0),
        "night_reason_distribution": compare_night.get("reason_distribution_on") if isinstance(compare_night.get("reason_distribution_on"), dict) else {},
        "main_compare_source_kind": str(compare_main.get("source_kind") or "missing"),
        "night_compare_source_kind": str(compare_night.get("source_kind") or "missing"),
        "main_l4_primary_reason": l4_main_reason,
        "main_gate_result": main_gate,
        "main_weekly_recommendation": main_weekly_rec,
        "main_weekly_recommendation_reason": main_weekly_reason,
        "night_gate_result": str(night_l5_summary.get("gate_result") or night_l5_summary.get("status") or ""),
        "night_weekly_recommendation": str(night_weekly_summary.get("recommendation") or ""),
        "night_weekly_recommendation_reason": str(night_weekly_summary.get("recommendation_reason") or ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build promote/hold decision from L4 challenge+sweep+L5 evidence")
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--main-sweep-summary", required=True)
    parser.add_argument("--main-l5-summary", required=True)
    parser.add_argument("--main-weekly-summary", required=True)
    parser.add_argument("--night-sweep-summary", required=True)
    parser.add_argument("--night-l5-summary", required=True)
    parser.add_argument("--night-weekly-summary", required=True)
    parser.add_argument("--min-delta-success-pp", type=float, default=5.0)
    parser.add_argument("--absolute-success-target-pct", type=float, default=85.0)
    parser.add_argument("--non-regression-tolerance-pp", type=float, default=0.0)
    parser.add_argument("--max-regression-worsen-pp", type=float, default=2.0)
    parser.add_argument("--max-physics-worsen-pp", type=float, default=2.0)
    parser.add_argument("--out", default="artifacts/agent_modelica_l4_uplift_evidence_v0/decision_summary.json")
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()

    summary = evaluate_l4_uplift_decision_v0(
        challenge_summary=_load_json(args.challenge_summary),
        main_sweep_summary=_load_json(args.main_sweep_summary),
        main_l5_summary=_load_json(args.main_l5_summary),
        main_weekly_summary=_load_json(args.main_weekly_summary),
        night_sweep_summary=_load_json(args.night_sweep_summary),
        night_l5_summary=_load_json(args.night_l5_summary),
        night_weekly_summary=_load_json(args.night_weekly_summary),
        min_delta_success_pp=float(args.min_delta_success_pp),
        absolute_success_target_pct=float(args.absolute_success_target_pct),
        non_regression_tolerance_pp=float(args.non_regression_tolerance_pp),
        max_regression_worsen_pp=float(args.max_regression_worsen_pp),
        max_physics_worsen_pp=float(args.max_physics_worsen_pp),
    )
    summary["inputs"] = {
        "challenge_summary": str(args.challenge_summary),
        "main_sweep_summary": str(args.main_sweep_summary),
        "main_l5_summary": str(args.main_l5_summary),
        "main_weekly_summary": str(args.main_weekly_summary),
        "night_sweep_summary": str(args.night_sweep_summary),
        "night_l5_summary": str(args.night_l5_summary),
        "night_weekly_summary": str(args.night_weekly_summary),
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "decision": summary.get("decision"),
                "primary_reason": summary.get("primary_reason"),
                "main_delta_success_at_k_pp": summary.get("main_delta_success_at_k_pp"),
                "infra_failure_count_total": summary.get("infra_failure_count_total"),
            }
        )
    )


if __name__ == "__main__":
    main()
