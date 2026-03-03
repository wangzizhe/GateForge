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


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        rows.append(json.loads(text))
    return rows


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True))
            f.write("\n")


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
        "# GateForge Scale Action Backlog History v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_total_p0_actions: `{payload.get('latest_total_p0_actions')}`",
        f"- avg_total_actions: `{payload.get('avg_total_actions')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append action backlog snapshots and emit history summary")
    parser.add_argument("--scale-execution-priority-board-summary", required=True)
    parser.add_argument("--family-gap-action-plan-summary", required=True)
    parser.add_argument("--failure-balance-backfill-plan-summary", required=True)
    parser.add_argument("--weekly-scale-milestone-checkpoint-summary", required=True)
    parser.add_argument("--ledger", default="artifacts/private_model_mutation_scale_batch_v1/state/action_backlog_history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_scale_action_backlog_history_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    board = _load_json(args.scale_execution_priority_board_summary)
    family_plan = _load_json(args.family_gap_action_plan_summary)
    failure_plan = _load_json(args.failure_balance_backfill_plan_summary)
    checkpoint = _load_json(args.weekly_scale_milestone_checkpoint_summary)

    reasons: list[str] = []
    if not board:
        reasons.append("scale_execution_priority_board_summary_missing")
    if not family_plan:
        reasons.append("family_gap_action_plan_summary_missing")
    if not failure_plan:
        reasons.append("failure_balance_backfill_plan_summary_missing")
    if not checkpoint:
        reasons.append("weekly_scale_milestone_checkpoint_summary_missing")

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    row = {
        "recorded_at_utc": now,
        "scale_board_status": str(board.get("status") or "UNKNOWN"),
        "scale_board_p0_tasks": _to_int(board.get("p0_tasks", 0)),
        "scale_board_total_tasks": _to_int(board.get("task_count", 0)),
        "family_plan_status": str(family_plan.get("status") or "UNKNOWN"),
        "family_plan_p0_actions": _to_int(family_plan.get("p0_actions", 0)),
        "family_plan_total_actions": _to_int(family_plan.get("total_actions", 0)),
        "failure_plan_status": str(failure_plan.get("status") or "UNKNOWN"),
        "failure_plan_p0_actions": _to_int(failure_plan.get("p0_actions", 0)),
        "failure_plan_total_actions": _to_int(failure_plan.get("total_actions", 0)),
        "checkpoint_status": str(checkpoint.get("status") or "UNKNOWN"),
        "checkpoint_score": round(_to_float(checkpoint.get("milestone_score", 0.0)), 4),
        "total_p0_actions": _to_int(board.get("p0_tasks", 0))
        + _to_int(family_plan.get("p0_actions", 0))
        + _to_int(failure_plan.get("p0_actions", 0)),
        "total_actions": _to_int(board.get("task_count", 0))
        + _to_int(family_plan.get("total_actions", 0))
        + _to_int(failure_plan.get("total_actions", 0)),
    }
    if not reasons:
        _append_jsonl(ledger_path, [row])

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) >= 2 else {}

    avg_total_actions = round(sum(_to_int(r.get("total_actions", 0)) for r in rows) / max(1, total), 4)
    avg_total_p0_actions = round(sum(_to_int(r.get("total_p0_actions", 0)) for r in rows) / max(1, total), 4)
    avg_checkpoint_score = round(sum(_to_float(r.get("checkpoint_score", 0.0)) for r in rows) / max(1, total), 4)
    delta_total_actions = _to_int(latest.get("total_actions", 0)) - _to_int(previous.get("total_actions", 0))
    delta_total_p0_actions = _to_int(latest.get("total_p0_actions", 0)) - _to_int(previous.get("total_p0_actions", 0))

    alerts: list[str] = []
    if str(latest.get("checkpoint_status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_checkpoint_not_pass")
    if total >= 2 and delta_total_p0_actions > 0:
        alerts.append("total_p0_actions_increasing")
    if total >= 3 and avg_total_p0_actions >= 2.0:
        alerts.append("avg_total_p0_actions_high")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": now,
        "status": status,
        "ledger_path": str(ledger_path),
        "total_records": total,
        "latest_total_actions": latest.get("total_actions"),
        "latest_total_p0_actions": latest.get("total_p0_actions"),
        "latest_checkpoint_score": latest.get("checkpoint_score"),
        "avg_total_actions": avg_total_actions,
        "avg_total_p0_actions": avg_total_p0_actions,
        "avg_checkpoint_score": avg_checkpoint_score,
        "delta_total_actions": delta_total_actions,
        "delta_total_p0_actions": delta_total_p0_actions,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_records": total, "latest_total_p0_actions": payload["latest_total_p0_actions"]}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
