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


def _write_json(path: str, payload: object) -> None:
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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Weekly Scale Milestone Checkpoint v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- milestone_score: `{payload.get('milestone_score')}`",
        f"- milestone_grade: `{payload.get('milestone_grade')}`",
        f"- top_actions_count: `{payload.get('top_actions_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 65:
        return "C"
    return "D"


def _collect_actions(*, gap: dict, family: dict, failure_balance: dict, board: dict) -> list[dict]:
    actions: list[dict] = []
    if _to_int(gap.get("gap_models", 0)) > 0:
        actions.append(
            {
                "action_id": "expand_real_model_pool",
                "priority": "P0",
                "reason": "model_pool_gap_open",
                "target": f"+{_to_int(gap.get('required_weekly_new_models', 0))}/week models",
            }
        )
    if _to_int(gap.get("gap_reproducible_mutations", 0)) > 0:
        actions.append(
            {
                "action_id": "expand_reproducible_mutation_execution",
                "priority": "P0",
                "reason": "reproducible_mutation_gap_open",
                "target": f"+{_to_int(gap.get('required_weekly_new_reproducible_mutations', 0))}/week reproducible mutations",
            }
        )
    if "covered_families_below_threshold" in (family.get("alerts") or []):
        actions.append(
            {
                "action_id": "close_family_coverage_gaps",
                "priority": "P1",
                "reason": "family_coverage_gap_open",
                "target": "increase model families covered",
            }
        )
    if "dominant_failure_type_share_high" in (failure_balance.get("alerts") or []):
        actions.append(
            {
                "action_id": "rebalance_failure_type_mix",
                "priority": "P1",
                "reason": "failure_type_dominance_high",
                "target": "reduce dominant failure-type share",
            }
        )
    if _to_int(board.get("p0_tasks", 0)) > 0:
        actions.append(
            {
                "action_id": "close_scale_board_p0_tasks",
                "priority": "P0",
                "reason": "execution_board_p0_present",
                "target": f"close_{_to_int(board.get('p0_tasks', 0))}_p0_tasks",
            }
        )
    actions.sort(key=lambda x: (str(x.get("priority") or "P9"), str(x.get("action_id") or "")))
    return actions[:3]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute weekly milestone checkpoint for scale moat progress")
    parser.add_argument("--scale-batch-summary", required=True)
    parser.add_argument("--scale-target-gap-summary", required=True)
    parser.add_argument("--scale-evidence-stamp-summary", required=True)
    parser.add_argument("--real-model-family-coverage-board-summary", required=True)
    parser.add_argument("--mutation-failure-type-balance-guard-summary", required=True)
    parser.add_argument("--scale-execution-priority-board-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_weekly_scale_milestone_checkpoint_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    batch = _load_json(args.scale_batch_summary)
    gap = _load_json(args.scale_target_gap_summary)
    evidence = _load_json(args.scale_evidence_stamp_summary)
    family = _load_json(args.real_model_family_coverage_board_summary)
    failure_balance = _load_json(args.mutation_failure_type_balance_guard_summary)
    board = _load_json(args.scale_execution_priority_board_summary)

    reasons: list[str] = []
    if not batch:
        reasons.append("scale_batch_summary_missing")
    if not gap:
        reasons.append("scale_target_gap_summary_missing")
    if not evidence:
        reasons.append("scale_evidence_stamp_summary_missing")
    if not family:
        reasons.append("real_model_family_coverage_board_summary_missing")
    if not failure_balance:
        reasons.append("mutation_failure_type_balance_guard_summary_missing")

    evidence_score = _to_float(evidence.get("evidence_score", 0.0))
    gap_progress = _to_float(gap.get("overall_progress_pct", 0.0))
    hardness = _to_float(batch.get("hard_moat_hardness_score", 0.0))
    family_entropy = _to_float(family.get("family_entropy", 0.0))
    failure_entropy = _to_float(failure_balance.get("expected_entropy", 0.0))

    milestone_score = round(
        (evidence_score * 0.35)
        + (gap_progress * 0.25)
        + (hardness * 0.2)
        + (min(100.0, family_entropy * 25.0) * 0.1)
        + (min(100.0, failure_entropy * 25.0) * 0.1),
        2,
    )
    milestone_grade = _grade(milestone_score)

    alerts: list[str] = []
    if str(batch.get("hard_moat_gates_status") or "") == "FAIL":
        alerts.append("hard_moat_gates_fail")
    if str(evidence.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("evidence_stamp_not_pass")
    if str(gap.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("scale_target_gap_not_pass")
    if str(family.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("family_coverage_not_pass")
    if str(failure_balance.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("failure_type_balance_not_pass")
    if _to_int(board.get("p0_tasks", 0)) > 0:
        alerts.append("execution_board_p0_tasks_present")
    if milestone_score < 70.0:
        alerts.append("milestone_score_low")

    top_actions = _collect_actions(gap=gap, family=family, failure_balance=failure_balance, board=board)

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "milestone_score": milestone_score,
        "milestone_grade": milestone_grade,
        "top_actions_count": len(top_actions),
        "top_actions": top_actions,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "signals": {
            "evidence_score": evidence_score,
            "gap_progress_pct": gap_progress,
            "hardness_score": hardness,
            "family_entropy": family_entropy,
            "failure_type_entropy": failure_entropy,
            "board_p0_tasks": _to_int(board.get("p0_tasks", 0)),
        },
        "sources": {
            "scale_batch_summary": args.scale_batch_summary,
            "scale_target_gap_summary": args.scale_target_gap_summary,
            "scale_evidence_stamp_summary": args.scale_evidence_stamp_summary,
            "real_model_family_coverage_board_summary": args.real_model_family_coverage_board_summary,
            "mutation_failure_type_balance_guard_summary": args.mutation_failure_type_balance_guard_summary,
            "scale_execution_priority_board_summary": args.scale_execution_priority_board_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "milestone_score": milestone_score, "top_actions_count": len(top_actions)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
