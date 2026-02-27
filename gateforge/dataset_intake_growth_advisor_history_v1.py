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


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Intake Growth Advisor History v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_status: `{payload.get('latest_status')}`",
        f"- latest_suggested_action: `{payload.get('latest_suggested_action')}`",
        f"- recovery_plan_rate: `{payload.get('recovery_plan_rate')}`",
        f"- targeted_patch_rate: `{payload.get('targeted_patch_rate')}`",
        f"- avg_backlog_action_count: `{payload.get('avg_backlog_action_count')}`",
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
    parser = argparse.ArgumentParser(description="Append intake growth advisor summaries and emit history")
    parser.add_argument("--record", action="append", default=[], help="intake growth advisor summary JSON path")
    parser.add_argument("--ledger", default="artifacts/dataset_intake_growth_advisor_history_v1/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_intake_growth_advisor_history_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)

    append_rows: list[dict] = []
    for path in args.record:
        payload = _load_json(path)
        advice = payload.get("advice") if isinstance(payload.get("advice"), dict) else {}
        append_rows.append(
            {
                "recorded_at_utc": now,
                "source_record_path": path,
                "status": str(payload.get("status") or "UNKNOWN"),
                "suggested_action": str(advice.get("suggested_action") or "unknown"),
                "priority": str(advice.get("priority") or "unknown"),
                "confidence": round(_to_float(advice.get("confidence", 0.0)), 2),
                "backlog_action_count": len(advice.get("backlog_actions") or []),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}
    action_counts = {
        "keep": 0,
        "execute_targeted_growth_patch": 0,
        "execute_growth_recovery_plan": 0,
        "unknown": 0,
    }
    status_counts = {"PASS": 0, "NEEDS_REVIEW": 0, "FAIL": 0, "UNKNOWN": 0}
    total_backlog_actions = 0
    for row in rows:
        action = str(row.get("suggested_action") or "unknown")
        action_counts[action] = action_counts.get(action, 0) + 1
        s = str(row.get("status") or "UNKNOWN")
        status_counts[s] = status_counts.get(s, 0) + 1
        total_backlog_actions += _to_int(row.get("backlog_action_count", 0))

    keep_rate = round(action_counts.get("keep", 0) / max(1, total), 4)
    targeted_patch_rate = round(action_counts.get("execute_targeted_growth_patch", 0) / max(1, total), 4)
    recovery_plan_rate = round(action_counts.get("execute_growth_recovery_plan", 0) / max(1, total), 4)
    avg_backlog_action_count = round(total_backlog_actions / max(1, total), 4)

    alerts: list[str] = []
    if str(latest.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_status_not_pass")
    if str(latest.get("suggested_action") or "") == "execute_growth_recovery_plan":
        alerts.append("latest_recovery_plan")
    if recovery_plan_rate >= 0.3 and total >= 3:
        alerts.append("recovery_plan_rate_high")
    if avg_backlog_action_count >= 4.0 and total >= 3:
        alerts.append("avg_backlog_action_count_high")

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
        "action_counts": action_counts,
        "latest_status": latest.get("status"),
        "latest_suggested_action": latest.get("suggested_action"),
        "latest_priority": latest.get("priority"),
        "latest_confidence": latest.get("confidence"),
        "keep_rate": keep_rate,
        "targeted_patch_rate": targeted_patch_rate,
        "recovery_plan_rate": recovery_plan_rate,
        "avg_backlog_action_count": avg_backlog_action_count,
        "alerts": alerts,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "total_records": total,
                "latest_suggested_action": latest.get("suggested_action"),
                "recovery_plan_rate": recovery_plan_rate,
            }
        )
    )


if __name__ == "__main__":
    main()
