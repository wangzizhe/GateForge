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


def _write_json(path: str, payload: object) -> None:
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
    advice = payload.get("advice") if isinstance(payload.get("advice"), dict) else {}
    lines = [
        "# GateForge Intake Growth Advisor v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- suggested_action: `{advice.get('suggested_action')}`",
        f"- confidence: `{advice.get('confidence')}`",
        f"- priority: `{advice.get('priority')}`",
        "",
        "## Backlog Actions",
        "",
    ]
    actions = advice.get("backlog_actions") if isinstance(advice.get("backlog_actions"), list) else []
    if actions:
        for action in actions:
            if isinstance(action, dict):
                lines.append(
                    f"- `{action.get('action_id')}` lane=`{action.get('lane')}` priority=`{action.get('priority')}` target=`{action.get('target')}`"
                )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _missing_lane_actions(matrix: dict) -> list[dict]:
    rows = matrix.get("missing_cells") if isinstance(matrix.get("missing_cells"), list) else []
    actions: list[dict] = []
    for idx, row in enumerate(rows[:8]):
        if not isinstance(row, dict):
            continue
        scale = str(row.get("model_scale") or "unknown")
        failure_type = str(row.get("failure_type") or "unknown")
        missing_mutations = _to_int(row.get("missing_mutations", 1))
        actions.append(
            {
                "action_id": f"lane_backfill_{idx+1}",
                "lane": f"{scale}::{failure_type}",
                "priority": "P1" if scale == "large" else "P2",
                "target": f"add_{max(1, missing_mutations)}_mutations",
                "reason": "matrix_missing_lane",
            }
        )
    return actions


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate next-week intake growth actions from intake and coverage signals")
    parser.add_argument("--real-model-intake-summary", required=True)
    parser.add_argument("--real-model-intake-weekly-target-guard-summary", default=None)
    parser.add_argument("--mutation-execution-matrix-summary", default=None)
    parser.add_argument("--failure-distribution-benchmark-v2-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_intake_growth_advisor_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    intake = _load_json(args.real_model_intake_summary)
    guard = _load_json(args.real_model_intake_weekly_target_guard_summary)
    matrix = _load_json(args.mutation_execution_matrix_summary)
    benchmark = _load_json(args.failure_distribution_benchmark_v2_summary)

    reasons: list[str] = []
    if not intake:
        reasons.append("real_model_intake_summary_missing")

    accepted_count = _to_int(intake.get("accepted_count", 0))
    accepted_large_count = _to_int(
        intake.get(
            "accepted_large_count",
            ((intake.get("accepted_scale_counts") or {}).get("large", 0))
            if isinstance(intake.get("accepted_scale_counts"), dict)
            else 0,
        )
    )
    reject_rate_pct = _to_float(intake.get("reject_rate_pct", 0.0))
    intake_target_status = str(intake.get("weekly_target_status") or "")
    guard_status = str(guard.get("status") or "")
    matrix_ratio = _to_float(matrix.get("matrix_execution_ratio_pct", 100.0))
    drift = _to_float(benchmark.get("failure_type_drift", 0.0))

    gaps: list[str] = []
    if accepted_count < 3:
        gaps.append("accepted_below_weekly_target")
    if accepted_large_count < 1:
        gaps.append("accepted_large_below_weekly_target")
    if reject_rate_pct > 45.0:
        gaps.append("reject_rate_above_target")
    if intake_target_status in {"NEEDS_REVIEW", "FAIL"}:
        gaps.append("intake_weekly_target_not_pass")
    if guard_status in {"NEEDS_REVIEW", "FAIL"}:
        gaps.append("guard_not_pass")
    if matrix_ratio < 85.0:
        gaps.append("mutation_matrix_coverage_low")
    if drift > 0.12:
        gaps.append("failure_distribution_drift_high")

    backlog_actions: list[dict] = []
    if "accepted_below_weekly_target" in gaps:
        backlog_actions.append(
            {
                "action_id": "add_candidates_general",
                "lane": "intake::all",
                "priority": "P1",
                "target": f"add_{max(1, 3 - accepted_count)}_accepted",
                "reason": "accepted_below_weekly_target",
            }
        )
    if "accepted_large_below_weekly_target" in gaps:
        backlog_actions.append(
            {
                "action_id": "add_candidates_large",
                "lane": "intake::large",
                "priority": "P0",
                "target": f"add_{max(1, 1 - accepted_large_count)}_large_accepted",
                "reason": "accepted_large_below_weekly_target",
            }
        )
    if "reject_rate_above_target" in gaps:
        backlog_actions.append(
            {
                "action_id": "reduce_reject_rate",
                "lane": "intake::quality",
                "priority": "P1",
                "target": "tighten_precheck_and_license_filter",
                "reason": "reject_rate_above_target",
            }
        )
    if "failure_distribution_drift_high" in gaps:
        backlog_actions.append(
            {
                "action_id": "stabilize_failure_distribution",
                "lane": "distribution::benchmark_v2",
                "priority": "P1",
                "target": "drift<=0.12_for_2_runs",
                "reason": "failure_distribution_drift_high",
            }
        )

    backlog_actions.extend(_missing_lane_actions(matrix))

    risk_score = 0
    if "accepted_below_weekly_target" in gaps:
        risk_score += 2
    if "accepted_large_below_weekly_target" in gaps:
        risk_score += 3
    if "reject_rate_above_target" in gaps:
        risk_score += 2
    if "mutation_matrix_coverage_low" in gaps:
        risk_score += 2
    if "failure_distribution_drift_high" in gaps:
        risk_score += 2

    suggested_action = "keep"
    priority = "P3"
    confidence = 0.62
    if risk_score >= 6:
        suggested_action = "execute_growth_recovery_plan"
        priority = "P0"
        confidence = 0.86
    elif risk_score >= 3:
        suggested_action = "execute_targeted_growth_patch"
        priority = "P1"
        confidence = 0.78

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif suggested_action != "keep":
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "gaps": sorted(set(gaps)),
        "advice": {
            "suggested_action": suggested_action,
            "priority": priority,
            "confidence": round(confidence, 2),
            "backlog_actions": backlog_actions[:12],
        },
        "signals": {
            "accepted_count": accepted_count,
            "accepted_large_count": accepted_large_count,
            "reject_rate_pct": round(reject_rate_pct, 2),
            "weekly_target_status": intake_target_status,
            "guard_status": guard_status,
            "matrix_execution_ratio_pct": round(matrix_ratio, 2),
            "failure_type_drift": round(drift, 6),
        },
        "reasons": sorted(set(reasons)),
        "sources": {
            "real_model_intake_summary": args.real_model_intake_summary,
            "real_model_intake_weekly_target_guard_summary": args.real_model_intake_weekly_target_guard_summary,
            "mutation_execution_matrix_summary": args.mutation_execution_matrix_summary,
            "failure_distribution_benchmark_v2_summary": args.failure_distribution_benchmark_v2_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "suggested_action": (payload.get("advice") or {}).get("suggested_action"),
                "backlog_actions": len(((payload.get("advice") or {}).get("backlog_actions") or [])),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
