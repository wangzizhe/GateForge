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
    lines = [
        "# GateForge Agent Modelica Acceptance Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- pass_count: `{payload.get('pass_count')}`",
        f"- needs_review_count: `{payload.get('needs_review_count')}`",
        f"- fail_count: `{payload.get('fail_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _time_threshold(scale: str, s: int, m: int, l: int) -> int:
    if scale == "large":
        return l
    if scale == "medium":
        return m
    return s


def _round_threshold(scale: str, s: int, m: int, l: int) -> int:
    if scale == "large":
        return l
    if scale == "medium":
        return m
    return s


def _hard_failed(rec: dict) -> bool:
    hard = rec.get("hard_checks") if isinstance(rec.get("hard_checks"), dict) else {}
    return not (
        bool(hard.get("check_model_pass"))
        and bool(hard.get("simulate_pass"))
        and bool(hard.get("physics_contract_pass"))
        and bool(hard.get("regression_pass"))
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply layered acceptance gate for modelica agent run contract")
    parser.add_argument("--run-results", required=True)
    parser.add_argument("--small-max-time-sec", type=int, default=300)
    parser.add_argument("--medium-max-time-sec", type=int, default=300)
    parser.add_argument("--large-max-time-sec", type=int, default=600)
    parser.add_argument("--small-max-rounds", type=int, default=5)
    parser.add_argument("--medium-max-rounds", type=int, default=5)
    parser.add_argument("--large-max-rounds", type=int, default=8)
    parser.add_argument("--out", default="artifacts/agent_modelica_acceptance_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    payload = _load_json(args.run_results)
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]
    reasons: list[str] = []
    if not records:
        reasons.append("run_records_empty")

    verdicts: list[dict] = []
    pass_count = 0
    needs_review_count = 0
    fail_count = 0
    counts_by_scale: dict[str, dict[str, int]] = {}

    for rec in records:
        scale = str(rec.get("scale") or "unknown").lower()
        rounds_used = int(rec.get("rounds_used", 0) or 0)
        elapsed_sec = int(rec.get("elapsed_sec", 0) or 0)
        hard_failed = _hard_failed(rec)
        max_time = _time_threshold(
            scale, int(args.small_max_time_sec), int(args.medium_max_time_sec), int(args.large_max_time_sec)
        )
        max_rounds = _round_threshold(
            scale, int(args.small_max_rounds), int(args.medium_max_rounds), int(args.large_max_rounds)
        )

        if hard_failed:
            decision = "FAIL"
            decision_reason = "hard_gate_failed"
        elif rounds_used > max_rounds or elapsed_sec > max_time:
            decision = "NEEDS_REVIEW"
            decision_reason = "soft_budget_exceeded"
        else:
            decision = "PASS"
            decision_reason = "meets_hard_and_soft_gates"

        if decision == "PASS":
            pass_count += 1
        elif decision == "NEEDS_REVIEW":
            needs_review_count += 1
        else:
            fail_count += 1

        bucket = counts_by_scale.setdefault(scale, {"PASS": 0, "NEEDS_REVIEW": 0, "FAIL": 0})
        bucket[decision] = int(bucket.get(decision, 0)) + 1
        verdicts.append(
            {
                "task_id": rec.get("task_id"),
                "scale": scale,
                "decision": decision,
                "decision_reason": decision_reason,
                "elapsed_sec": elapsed_sec,
                "rounds_used": rounds_used,
                "max_time_sec": max_time,
                "max_rounds": max_rounds,
            }
        )

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif fail_count > 0:
        status = "FAIL"
    elif needs_review_count > 0:
        status = "NEEDS_REVIEW"

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_tasks": len(records),
        "pass_count": pass_count,
        "needs_review_count": needs_review_count,
        "fail_count": fail_count,
        "counts_by_scale": counts_by_scale,
        "verdicts": verdicts,
        "reasons": reasons,
        "sources": {"run_results": args.run_results},
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "pass_count": pass_count, "fail_count": fail_count}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

