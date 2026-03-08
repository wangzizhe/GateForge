from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


ALLOWED_L5_REASONS = {
    "run_summary_missing",
    "run_results_missing",
    "l3_quality_summary_missing",
    "l4_ab_compare_summary_missing",
    "attempts_missing",
    "delta_success_at_k_below_threshold",
    "physics_fail_rate_worsened_beyond_threshold",
    "regression_fail_rate_worsened_beyond_threshold",
    "infra_failure_count_not_zero",
    "l3_parse_coverage_below_threshold",
    "l3_type_match_rate_below_threshold",
    "l3_stage_match_rate_below_threshold",
    "l3_diagnostic_gate_not_pass",
    "l3_diagnostic_gate_needs_review",
    "reason_enum_unknown",
}


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


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
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
    except (TypeError, ValueError):
        return default


def _ratio(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round((float(num) / float(den)) * 100.0, 2)


def _median(values: list[float]) -> float:
    rows = [float(x) for x in values if isinstance(x, (int, float))]
    if not rows:
        return 0.0
    return round(float(statistics.median(rows)), 2)


def _infer_infra_reason(stderr: str, reason: str, log_excerpt: str) -> str:
    text = " ".join([str(stderr or ""), str(reason or ""), str(log_excerpt or "")]).lower()
    if "timeoutexpired" in text or "timed out" in text or "live_executor_timeout" in text:
        return "timeout"
    if "permission denied while trying to connect to the docker api" in text:
        return "docker_permission_denied"
    if "includes invalid characters for a local volume name" in text:
        return "docker_volume_mount_invalid"
    if "failed to load package modelica" in text:
        return "msl_load_failed"
    if "model_path_missing" in text or "no such file or directory" in text:
        return "path_not_found"
    if "mount" in text and "permission denied" in text:
        return "mount_permission_denied"
    return ""


def _summarize_run_results(run_results_payload: dict) -> dict:
    records = run_results_payload.get("records") if isinstance(run_results_payload.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]

    total = len(records)
    success = len([x for x in records if bool(x.get("passed"))])
    regression_fail_count = len([x for x in records if not bool((x.get("hard_checks") or {}).get("regression_pass"))])
    physics_fail_count = len([x for x in records if not bool((x.get("hard_checks") or {}).get("physics_contract_pass"))])

    rounds: list[float] = []
    times: list[float] = []
    attempt_count = 0
    infra_count = 0
    infra_by_reason: dict[str, int] = {}

    for rec in records:
        rounds.append(_to_float(rec.get("rounds_used"), 0.0))
        times.append(_to_float(rec.get("elapsed_sec"), 0.0))
        attempts = rec.get("attempts") if isinstance(rec.get("attempts"), list) else []
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            attempt_count += 1
            infra = _infer_infra_reason(
                stderr=str(attempt.get("stderr_snippet") or ""),
                reason=str(attempt.get("reason") or ""),
                log_excerpt=str(attempt.get("log_excerpt") or ""),
            )
            if infra:
                infra_count += 1
                infra_by_reason[infra] = int(infra_by_reason.get(infra, 0)) + 1

    return {
        "record_count": total,
        "success_count": success,
        "success_at_k_pct": _ratio(success, total),
        "physics_fail_rate_pct": _ratio(physics_fail_count, total),
        "regression_fail_rate_pct": _ratio(regression_fail_count, total),
        "median_rounds": _median(rounds),
        "median_time_to_pass_sec": _median(times),
        "attempt_count": attempt_count,
        "infra_failure_count": infra_count,
        "infra_failure_by_reason": dict(sorted(infra_by_reason.items())),
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    thresholds = payload.get("thresholds") if isinstance(payload.get("thresholds"), dict) else {}
    cost_metrics = payload.get("cost_metrics") if isinstance(payload.get("cost_metrics"), dict) else {}
    lines = [
        "# Agent Modelica L5 Eval v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- gate_result: `{payload.get('gate_result')}`",
        f"- gate_mode: `{payload.get('gate_mode')}`",
        f"- success_at_k_pct: `{payload.get('success_at_k_pct')}`",
        f"- delta_success_at_k_pp: `{payload.get('delta_success_at_k_pp')}`",
        f"- physics_fail_rate_pct: `{payload.get('physics_fail_rate_pct')}`",
        f"- regression_fail_rate_pct: `{payload.get('regression_fail_rate_pct')}`",
        f"- infra_failure_count: `{payload.get('infra_failure_count')}`",
        f"- l3_parse_coverage_pct: `{payload.get('l3_parse_coverage_pct')}`",
        f"- l3_type_match_rate_pct: `{payload.get('l3_type_match_rate_pct')}`",
        f"- l3_stage_match_rate_pct: `{payload.get('l3_stage_match_rate_pct')}`",
        f"- l3_gate_status: `{payload.get('l3_diagnostic_gate_status')}`",
        f"- primary_reason: `{payload.get('primary_reason')}`",
        "",
        "## Cost Metrics",
        "",
        f"- median_rounds: `{cost_metrics.get('median_rounds', 0.0)}`",
        f"- median_time_to_pass_sec: `{cost_metrics.get('median_time_to_pass_sec', 0.0)}`",
        "",
        "## Thresholds",
        "",
        f"- min_delta_success_at_k_pp: `{thresholds.get('min_delta_success_at_k_pp')}`",
        f"- max_physics_fail_rate_worsen_pp: `{thresholds.get('max_physics_fail_rate_worsen_pp')}`",
        f"- max_regression_fail_rate_worsen_pp: `{thresholds.get('max_regression_fail_rate_worsen_pp')}`",
        f"- infra_failure_count_must_equal: `{thresholds.get('infra_failure_count_must_equal')}`",
        f"- min_l3_parse_coverage_pct: `{thresholds.get('min_l3_parse_coverage_pct')}`",
        f"- min_l3_type_match_rate_pct: `{thresholds.get('min_l3_type_match_rate_pct')}`",
        f"- min_l3_stage_match_rate_pct: `{thresholds.get('min_l3_stage_match_rate_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def evaluate_l5_eval_v1(
    *,
    run_summary: dict,
    run_results: dict,
    l3_quality_summary: dict,
    l3_gate_summary: dict,
    l4_ab_compare_summary: dict,
    gate_mode: str = "strict",
    min_delta_success_at_k_pp: float = 5.0,
    max_physics_fail_rate_worsen_pp: float = 2.0,
    max_regression_fail_rate_worsen_pp: float = 2.0,
    infra_failure_count_must_equal: int = 0,
    min_l3_parse_coverage_pct: float = 95.0,
    min_l3_type_match_rate_pct: float = 70.0,
    min_l3_stage_match_rate_pct: float = 70.0,
    additional_reasons: list[str] | None = None,
) -> dict:
    run_results_summary = _summarize_run_results(run_results)

    l4_on = l4_ab_compare_summary.get("on") if isinstance(l4_ab_compare_summary.get("on"), dict) else {}
    l4_off = l4_ab_compare_summary.get("off") if isinstance(l4_ab_compare_summary.get("off"), dict) else {}
    l4_delta = l4_ab_compare_summary.get("delta") if isinstance(l4_ab_compare_summary.get("delta"), dict) else {}

    success_at_k_pct = _to_float(l4_on.get("success_at_k_pct"), _to_float(run_summary.get("success_at_k_pct"), run_results_summary["success_at_k_pct"]))
    baseline_success_at_k_pct = _to_float(l4_off.get("success_at_k_pct"), success_at_k_pct)
    delta_success_at_k_pp = _to_float(l4_delta.get("success_at_k_pp"), round(success_at_k_pct - baseline_success_at_k_pct, 2))

    physics_fail_rate_pct = _to_float(l4_on.get("physics_fail_rate_pct"), run_results_summary["physics_fail_rate_pct"])
    baseline_physics_fail_rate_pct = _to_float(l4_off.get("physics_fail_rate_pct"), physics_fail_rate_pct)
    delta_physics_fail_rate_pp = round(physics_fail_rate_pct - baseline_physics_fail_rate_pct, 2)

    regression_fail_rate_pct = _to_float(l4_on.get("regression_fail_rate_pct"), run_results_summary["regression_fail_rate_pct"])
    baseline_regression_fail_rate_pct = _to_float(l4_off.get("regression_fail_rate_pct"), regression_fail_rate_pct)
    delta_regression_fail_rate_pp = round(regression_fail_rate_pct - baseline_regression_fail_rate_pct, 2)

    infra_failure_count = _to_int(l4_on.get("infra_failure_count"), run_results_summary["infra_failure_count"])
    infra_failure_by_reason = (
        l4_on.get("infra_failure_by_reason")
        if isinstance(l4_on.get("infra_failure_by_reason"), dict)
        else run_results_summary.get("infra_failure_by_reason")
    )
    if not isinstance(infra_failure_by_reason, dict):
        infra_failure_by_reason = {}

    l3_parse = _to_float(
        l3_quality_summary.get("parse_coverage_pct"),
        _to_float(l3_gate_summary.get("parse_coverage_pct"), 0.0),
    )
    l3_type = _to_float(
        l3_quality_summary.get("canonical_type_match_rate_pct"),
        _to_float(l3_quality_summary.get("type_match_rate_pct"), _to_float(l3_gate_summary.get("canonical_type_match_rate_pct"), 0.0)),
    )
    l3_stage = _to_float(
        l3_quality_summary.get("stage_match_rate_pct"),
        _to_float(l3_gate_summary.get("stage_match_rate_pct"), 0.0),
    )
    l3_low_conf = _to_float(
        l3_quality_summary.get("low_confidence_rate_pct"),
        _to_float(l3_gate_summary.get("low_confidence_rate_pct"), 0.0),
    )
    l3_gate_status = str(l3_gate_summary.get("status") or "").strip() or "UNKNOWN"

    median_rounds = _to_float(run_summary.get("median_repair_rounds"), run_results_summary.get("median_rounds", 0.0))
    median_time = _to_float(run_summary.get("median_time_to_pass_sec"), run_results_summary.get("median_time_to_pass_sec", 0.0))

    hard_reasons: list[str] = []
    soft_reasons: list[str] = []

    if not run_summary:
        hard_reasons.append("run_summary_missing")
    if not run_results:
        hard_reasons.append("run_results_missing")
    if not l3_quality_summary:
        hard_reasons.append("l3_quality_summary_missing")
    if not l4_ab_compare_summary:
        hard_reasons.append("l4_ab_compare_summary_missing")

    if _to_int(run_results_summary.get("attempt_count"), 0) <= 0:
        hard_reasons.append("attempts_missing")

    if delta_success_at_k_pp < float(min_delta_success_at_k_pp):
        hard_reasons.append("delta_success_at_k_below_threshold")
    if delta_physics_fail_rate_pp > float(max_physics_fail_rate_worsen_pp):
        hard_reasons.append("physics_fail_rate_worsened_beyond_threshold")
    if delta_regression_fail_rate_pp > float(max_regression_fail_rate_worsen_pp):
        hard_reasons.append("regression_fail_rate_worsened_beyond_threshold")
    if infra_failure_count != int(infra_failure_count_must_equal):
        hard_reasons.append("infra_failure_count_not_zero")

    if l3_parse < float(min_l3_parse_coverage_pct):
        hard_reasons.append("l3_parse_coverage_below_threshold")
    if l3_type < float(min_l3_type_match_rate_pct):
        hard_reasons.append("l3_type_match_rate_below_threshold")
    if l3_stage < float(min_l3_stage_match_rate_pct):
        hard_reasons.append("l3_stage_match_rate_below_threshold")

    if l3_gate_status in {"FAIL"}:
        hard_reasons.append("l3_diagnostic_gate_not_pass")
    elif l3_gate_status in {"NEEDS_REVIEW", "SKIPPED", "UNKNOWN", ""}:
        soft_reasons.append("l3_diagnostic_gate_needs_review")

    gate_mode_norm = str(gate_mode or "strict").strip().lower()
    if gate_mode_norm not in {"strict", "observe"}:
        gate_mode_norm = "strict"

    reasons = sorted(set(hard_reasons + soft_reasons))
    extra = [str(x).strip() for x in (additional_reasons or []) if str(x).strip()]
    reasons = sorted(set(reasons + extra))
    unknown_reasons = [x for x in reasons if x not in ALLOWED_L5_REASONS]
    if unknown_reasons:
        if gate_mode_norm == "strict":
            if "reason_enum_unknown" not in hard_reasons:
                hard_reasons.append("reason_enum_unknown")
        else:
            if "reason_enum_unknown" not in soft_reasons:
                soft_reasons.append("reason_enum_unknown")
        reasons = sorted(set(reasons + ["reason_enum_unknown"]))

    if gate_mode_norm == "observe":
        gate_result = "PASS" if not reasons else "NEEDS_REVIEW"
    else:
        if hard_reasons:
            gate_result = "FAIL"
        elif soft_reasons:
            gate_result = "NEEDS_REVIEW"
        else:
            gate_result = "PASS"

    summary = {
        "schema_version": "agent_modelica_l5_eval_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": gate_result,
        "gate_result": gate_result,
        "gate_mode": gate_mode_norm,
        "success_at_k_pct": success_at_k_pct,
        "baseline_success_at_k_pct": baseline_success_at_k_pct,
        "delta_success_at_k_pp": delta_success_at_k_pp,
        "physics_fail_rate_pct": physics_fail_rate_pct,
        "baseline_physics_fail_rate_pct": baseline_physics_fail_rate_pct,
        "delta_physics_fail_rate_pp": delta_physics_fail_rate_pp,
        "regression_fail_rate_pct": regression_fail_rate_pct,
        "baseline_regression_fail_rate_pct": baseline_regression_fail_rate_pct,
        "delta_regression_fail_rate_pp": delta_regression_fail_rate_pp,
        "infra_failure_count": infra_failure_count,
        "infra_failure_by_reason": dict(sorted({str(k): _to_int(v) for k, v in infra_failure_by_reason.items()}.items())),
        "l3_diagnostic_gate_status": l3_gate_status,
        "l3_parse_coverage_pct": l3_parse,
        "l3_type_match_rate_pct": l3_type,
        "l3_stage_match_rate_pct": l3_stage,
        "l3_low_confidence_rate_pct": l3_low_conf,
        "cost_metrics": {
            "median_rounds": median_rounds,
            "median_time_to_pass_sec": median_time,
        },
        "run_results_stats": run_results_summary,
        "thresholds": {
            "min_delta_success_at_k_pp": float(min_delta_success_at_k_pp),
            "max_physics_fail_rate_worsen_pp": float(max_physics_fail_rate_worsen_pp),
            "max_regression_fail_rate_worsen_pp": float(max_regression_fail_rate_worsen_pp),
            "infra_failure_count_must_equal": int(infra_failure_count_must_equal),
            "min_l3_parse_coverage_pct": float(min_l3_parse_coverage_pct),
            "min_l3_type_match_rate_pct": float(min_l3_type_match_rate_pct),
            "min_l3_stage_match_rate_pct": float(min_l3_stage_match_rate_pct),
        },
        "reasons": reasons,
        "primary_reason": reasons[0] if reasons else "none",
        "unknown_reasons": sorted(set(unknown_reasons)),
        "reason_enum": sorted(ALLOWED_L5_REASONS),
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate L5 gate metrics from run/L3/L4 artifacts")
    parser.add_argument("--run-summary", required=True)
    parser.add_argument("--run-results", required=True)
    parser.add_argument("--l3-quality-summary", required=True)
    parser.add_argument("--l3-gate-summary", required=True)
    parser.add_argument("--l4-ab-compare-summary", required=True)
    parser.add_argument("--gate-mode", default="strict", choices=["strict", "observe"])
    parser.add_argument("--min-delta-success-at-k-pp", type=float, default=5.0)
    parser.add_argument("--max-physics-fail-rate-worsen-pp", type=float, default=2.0)
    parser.add_argument("--max-regression-fail-rate-worsen-pp", type=float, default=2.0)
    parser.add_argument("--infra-failure-count-must-equal", type=int, default=0)
    parser.add_argument("--min-l3-parse-coverage-pct", type=float, default=95.0)
    parser.add_argument("--min-l3-type-match-rate-pct", type=float, default=70.0)
    parser.add_argument("--min-l3-stage-match-rate-pct", type=float, default=70.0)
    parser.add_argument("--additional-reasons-json", default="")
    parser.add_argument("--out", default="artifacts/agent_modelica_l5_eval_v1/l5_eval_summary.json")
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()

    run_summary = _load_json(args.run_summary)
    run_results = _load_json(args.run_results)
    l3_quality_summary = _load_json(args.l3_quality_summary)
    l3_gate_summary = _load_json(args.l3_gate_summary)
    l4_ab_compare_summary = _load_json(args.l4_ab_compare_summary)
    additional_reasons: list[str] = []
    if str(args.additional_reasons_json).strip():
        try:
            parsed = json.loads(str(args.additional_reasons_json))
        except Exception:
            parsed = []
        if isinstance(parsed, list):
            additional_reasons = [str(x).strip() for x in parsed if str(x).strip()]

    summary = evaluate_l5_eval_v1(
        run_summary=run_summary,
        run_results=run_results,
        l3_quality_summary=l3_quality_summary,
        l3_gate_summary=l3_gate_summary,
        l4_ab_compare_summary=l4_ab_compare_summary,
        gate_mode=str(args.gate_mode),
        min_delta_success_at_k_pp=float(args.min_delta_success_at_k_pp),
        max_physics_fail_rate_worsen_pp=float(args.max_physics_fail_rate_worsen_pp),
        max_regression_fail_rate_worsen_pp=float(args.max_regression_fail_rate_worsen_pp),
        infra_failure_count_must_equal=int(args.infra_failure_count_must_equal),
        min_l3_parse_coverage_pct=float(args.min_l3_parse_coverage_pct),
        min_l3_type_match_rate_pct=float(args.min_l3_type_match_rate_pct),
        min_l3_stage_match_rate_pct=float(args.min_l3_stage_match_rate_pct),
        additional_reasons=additional_reasons,
    )
    summary["inputs"] = {
        "run_summary": str(args.run_summary),
        "run_results": str(args.run_results),
        "l3_quality_summary": str(args.l3_quality_summary),
        "l3_gate_summary": str(args.l3_gate_summary),
        "l4_ab_compare_summary": str(args.l4_ab_compare_summary),
        "additional_reasons_json": str(args.additional_reasons_json or ""),
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "gate_result": summary.get("gate_result"),
                "success_at_k_pct": summary.get("success_at_k_pct"),
                "delta_success_at_k_pp": summary.get("delta_success_at_k_pp"),
                "infra_failure_count": summary.get("infra_failure_count"),
            }
        )
    )
    if str(summary.get("status") or "") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
