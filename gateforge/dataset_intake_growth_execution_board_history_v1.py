from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        rows.append(json.loads(s))
    return rows


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True))
            f.write("\n")


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
        "# GateForge Intake Growth Execution Board History v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_board_status: `{payload.get('latest_board_status')}`",
        f"- avg_execution_score: `{payload.get('avg_execution_score')}`",
        f"- critical_open_tasks_rate: `{payload.get('critical_open_tasks_rate')}`",
        f"- avg_projected_weeks_to_target: `{payload.get('avg_projected_weeks_to_target')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
    if alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append intake growth execution board summaries and emit history")
    parser.add_argument("--record", action="append", default=[], help="intake growth execution board summary JSON path")
    parser.add_argument("--ledger", default="artifacts/dataset_intake_growth_execution_board_history_v1/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_intake_growth_execution_board_history_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)

    append_rows: list[dict] = []
    for path in args.record:
        payload = _load_json(path)
        alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
        append_rows.append(
            {
                "recorded_at_utc": now,
                "source_record_path": path,
                "status": str(payload.get("status") or "UNKNOWN"),
                "execution_score": round(_to_float(payload.get("execution_score", 0.0)), 4),
                "critical_open_tasks": _to_int(payload.get("critical_open_tasks", 0)),
                "projected_weeks_to_target": _to_int(payload.get("projected_weeks_to_target", 0)),
                "task_count": _to_int(payload.get("task_count", 0)),
                "alerts_count": len(alerts),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}

    status_counts = {"PASS": 0, "NEEDS_REVIEW": 0, "FAIL": 0, "UNKNOWN": 0}
    total_execution_score = 0.0
    critical_open_records = 0
    total_projected_weeks = 0
    total_task_count = 0
    total_alerts_count = 0
    for row in rows:
        status = str(row.get("status") or "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
        total_execution_score += _to_float(row.get("execution_score", 0.0))
        if _to_int(row.get("critical_open_tasks", 0)) > 0:
            critical_open_records += 1
        total_projected_weeks += _to_int(row.get("projected_weeks_to_target", 0))
        total_task_count += _to_int(row.get("task_count", 0))
        total_alerts_count += _to_int(row.get("alerts_count", 0))

    avg_execution_score = round(total_execution_score / max(1, total), 4)
    critical_open_tasks_rate = round(critical_open_records / max(1, total), 4)
    avg_projected_weeks_to_target = round(total_projected_weeks / max(1, total), 4)
    avg_task_count = round(total_task_count / max(1, total), 4)
    avg_alerts_count = round(total_alerts_count / max(1, total), 4)

    alerts: list[str] = []
    latest_status = str(latest.get("status") or "UNKNOWN")
    if latest_status in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_board_status_not_pass")
    if avg_execution_score < 75.0 and total >= 3:
        alerts.append("avg_execution_score_low")
    if critical_open_tasks_rate >= 0.3 and total >= 3:
        alerts.append("critical_open_tasks_rate_high")
    if avg_projected_weeks_to_target > 1.0 and total >= 3:
        alerts.append("avg_projected_weeks_to_target_high")

    status = "PASS"
    if alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": now,
        "status": status,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "status_counts": status_counts,
        "latest_board_status": latest.get("status"),
        "latest_execution_score": _to_float(latest.get("execution_score", 0.0)),
        "latest_critical_open_tasks": _to_int(latest.get("critical_open_tasks", 0)),
        "latest_projected_weeks_to_target": _to_int(latest.get("projected_weeks_to_target", 0)),
        "avg_execution_score": avg_execution_score,
        "critical_open_tasks_rate": critical_open_tasks_rate,
        "avg_projected_weeks_to_target": avg_projected_weeks_to_target,
        "avg_task_count": avg_task_count,
        "avg_alerts_count": avg_alerts_count,
        "alerts": alerts,
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "total_records": total,
                "avg_execution_score": avg_execution_score,
                "critical_open_tasks_rate": critical_open_tasks_rate,
            }
        )
    )


if __name__ == "__main__":
    main()
