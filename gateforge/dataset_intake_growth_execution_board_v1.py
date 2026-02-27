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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


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
        "# GateForge Intake Growth Execution Board v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- execution_score: `{payload.get('execution_score')}`",
        f"- critical_open_tasks: `{payload.get('critical_open_tasks')}`",
        f"- projected_weeks_to_target: `{payload.get('projected_weeks_to_target')}`",
        "",
        "## Tasks",
        "",
    ]
    tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    if tasks:
        for t in tasks:
            if not isinstance(t, dict):
                continue
            lines.append(
                f"- `{t.get('task_id')}` priority=`{t.get('priority')}` lane=`{t.get('lane')}` target=`{t.get('target')}`"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build executable intake growth board from advisor and evidence signals")
    parser.add_argument("--intake-growth-advisor-summary", required=True)
    parser.add_argument("--intake-growth-advisor-history-summary", default=None)
    parser.add_argument("--intake-growth-advisor-history-trend-summary", default=None)
    parser.add_argument("--real-model-intake-summary", default=None)
    parser.add_argument("--mutation-execution-matrix-summary", default=None)
    parser.add_argument("--failure-distribution-benchmark-v2-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_intake_growth_execution_board_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    advisor = _load_json(args.intake_growth_advisor_summary)
    history = _load_json(args.intake_growth_advisor_history_summary)
    history_trend = _load_json(args.intake_growth_advisor_history_trend_summary)
    intake = _load_json(args.real_model_intake_summary)
    matrix = _load_json(args.mutation_execution_matrix_summary)
    benchmark = _load_json(args.failure_distribution_benchmark_v2_summary)

    reasons: list[str] = []
    if not advisor:
        reasons.append("intake_growth_advisor_summary_missing")

    advice = advisor.get("advice") if isinstance(advisor.get("advice"), dict) else {}
    tasks = advice.get("backlog_actions") if isinstance(advice.get("backlog_actions"), list) else []

    accepted_count = _to_int(intake.get("accepted_count", 0))
    accepted_large = _to_int(
        intake.get(
            "accepted_large_count",
            ((intake.get("accepted_scale_counts") or {}).get("large", 0)) if isinstance(intake.get("accepted_scale_counts"), dict) else 0,
        )
    )
    reject_rate_pct = _to_float(intake.get("reject_rate_pct", 0.0))
    matrix_ratio = _to_float(matrix.get("matrix_execution_ratio_pct", 100.0))
    drift = _to_float(benchmark.get("failure_type_drift", 0.0))

    open_tasks = len(tasks)
    critical_open_tasks = len([x for x in tasks if isinstance(x, dict) and str(x.get("priority") or "") == "P0"])

    execution_score = 80.0
    execution_score += min(8.0, accepted_count * 1.5)
    execution_score += min(6.0, accepted_large * 2.5)
    execution_score -= min(12.0, max(0.0, reject_rate_pct - 25.0) * 0.6)
    execution_score += min(6.0, max(0.0, matrix_ratio - 80.0) * 0.3)
    execution_score -= min(8.0, max(0.0, drift - 0.12) * 40.0)
    execution_score -= min(10.0, open_tasks * 1.5)
    execution_score = round(max(0.0, min(100.0, execution_score)), 2)

    projected_weeks_to_target = 0
    if accepted_count < 3:
        projected_weeks_to_target = max(projected_weeks_to_target, 3 - accepted_count)
    if accepted_large < 1:
        projected_weeks_to_target = max(projected_weeks_to_target, 1)
    if open_tasks >= 6:
        projected_weeks_to_target = max(projected_weeks_to_target, 3)
    elif open_tasks >= 3:
        projected_weeks_to_target = max(projected_weeks_to_target, 2)

    board_alerts: list[str] = []
    if critical_open_tasks > 0:
        board_alerts.append("critical_open_tasks_present")
    if reject_rate_pct > 45.0:
        board_alerts.append("reject_rate_high")
    if matrix_ratio < 85.0:
        board_alerts.append("matrix_execution_ratio_low")
    if drift > 0.12:
        board_alerts.append("failure_distribution_drift_high")
    if str((history_trend.get("status") or "")) in {"NEEDS_REVIEW", "FAIL"}:
        board_alerts.append("history_trend_not_pass")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif board_alerts or execution_score < 72.0:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "execution_score": execution_score,
        "task_count": open_tasks,
        "critical_open_tasks": critical_open_tasks,
        "projected_weeks_to_target": projected_weeks_to_target,
        "tasks": tasks,
        "alerts": board_alerts,
        "signals": {
            "accepted_count": accepted_count,
            "accepted_large_count": accepted_large,
            "reject_rate_pct": round(reject_rate_pct, 2),
            "matrix_execution_ratio_pct": round(matrix_ratio, 2),
            "failure_type_drift": round(drift, 6),
            "history_status": history.get("status"),
            "history_trend_status": history_trend.get("status"),
        },
        "reasons": sorted(set(reasons)),
        "sources": {
            "intake_growth_advisor_summary": args.intake_growth_advisor_summary,
            "intake_growth_advisor_history_summary": args.intake_growth_advisor_history_summary,
            "intake_growth_advisor_history_trend_summary": args.intake_growth_advisor_history_trend_summary,
            "real_model_intake_summary": args.real_model_intake_summary,
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
                "execution_score": execution_score,
                "critical_open_tasks": critical_open_tasks,
                "projected_weeks_to_target": projected_weeks_to_target,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
