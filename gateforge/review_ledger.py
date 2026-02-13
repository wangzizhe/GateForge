from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def append_review_ledger(ledger_path: str, record: dict) -> None:
    p = Path(ledger_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")


def load_review_ledger(ledger_path: str) -> list[dict]:
    p = Path(ledger_path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def summarize_review_ledger(rows: list[dict]) -> dict:
    status_counter = Counter()
    reviewer_counter = Counter()
    reason_counter = Counter()
    risk_counter = Counter()
    risk_status_counter: dict[str, Counter] = {}
    date_counter = Counter()
    for row in rows:
        status = row.get("final_status")
        reviewer = row.get("reviewer")
        risk = row.get("risk_level")
        recorded_at = row.get("recorded_at_utc")
        if isinstance(status, str):
            status_counter[status] += 1
            if isinstance(risk, str) and risk.strip():
                risk_counter[risk] += 1
                if risk not in risk_status_counter:
                    risk_status_counter[risk] = Counter()
                risk_status_counter[risk][status] += 1
        if isinstance(reviewer, str) and reviewer.strip():
            reviewer_counter[reviewer] += 1
        if isinstance(recorded_at, str):
            try:
                date_key = _parse_utc(recorded_at).date().isoformat()
                date_counter[date_key] += 1
            except Exception:
                pass
        for reason in row.get("final_reasons", []) or []:
            if isinstance(reason, str):
                prefix = reason.split(":", 1)[0]
                reason_counter[prefix] += 1
    total = len(rows)
    pass_count = int(status_counter.get("PASS", 0))
    fail_count = int(status_counter.get("FAIL", 0))
    needs_review_count = int(status_counter.get("NEEDS_REVIEW", 0))
    approval_rate = round(pass_count / total, 4) if total else 0.0
    fail_rate = round(fail_count / total, 4) if total else 0.0

    recent_days = sorted(date_counter.keys())[-7:]
    volume_by_day = [{"date": day, "count": int(date_counter.get(day, 0))} for day in recent_days]

    by_risk: dict[str, dict[str, int]] = {}
    for risk, counter in risk_status_counter.items():
        by_risk[risk] = {k: int(v) for k, v in counter.items()}
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_records": len(rows),
        "status_counts": dict(status_counter),
        "reviewer_counts": dict(reviewer_counter),
        "reason_prefix_counts": dict(reason_counter),
        "risk_level_counts": dict(risk_counter),
        "kpis": {
            "approval_rate": approval_rate,
            "fail_rate": fail_rate,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "needs_review_count": needs_review_count,
            "by_risk_status_counts": by_risk,
            "review_volume_last_7_days": volume_by_day,
        },
    }


def filter_review_ledger(
    rows: list[dict],
    *,
    proposal_id: str | None = None,
    reviewer: str | None = None,
    final_status: str | None = None,
    since_utc: str | None = None,
    until_utc: str | None = None,
) -> list[dict]:
    since_dt = _parse_utc(since_utc) if since_utc else None
    until_dt = _parse_utc(until_utc) if until_utc else None

    out: list[dict] = []
    for row in rows:
        if proposal_id and row.get("proposal_id") != proposal_id:
            continue
        if reviewer and row.get("reviewer") != reviewer:
            continue
        if final_status and row.get("final_status") != final_status:
            continue
        if since_dt or until_dt:
            recorded = row.get("recorded_at_utc")
            if not isinstance(recorded, str):
                continue
            rec_dt = _parse_utc(recorded)
            if since_dt and rec_dt < since_dt:
                continue
            if until_dt and rec_dt > until_dt:
                continue
        out.append(row)
    return out


def write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# GateForge Review Ledger Summary",
        "",
        f"- generated_at_utc: `{summary.get('generated_at_utc')}`",
        f"- total_records: `{summary.get('total_records')}`",
        "",
        "## Status Counts",
        "",
    ]
    status_counts = summary.get("status_counts", {})
    if status_counts:
        for k in sorted(status_counts.keys()):
            lines.append(f"- {k}: `{status_counts[k]}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Reviewer Counts", ""])
    reviewer_counts = summary.get("reviewer_counts", {})
    if reviewer_counts:
        for k in sorted(reviewer_counts.keys()):
            lines.append(f"- {k}: `{reviewer_counts[k]}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Reason Prefix Counts", ""])
    reason_counts = summary.get("reason_prefix_counts", {})
    if reason_counts:
        for k in sorted(reason_counts.keys()):
            lines.append(f"- {k}: `{reason_counts[k]}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## KPI Snapshot", ""])
    kpis = summary.get("kpis", {})
    lines.append(f"- approval_rate: `{kpis.get('approval_rate', 0.0)}`")
    lines.append(f"- fail_rate: `{kpis.get('fail_rate', 0.0)}`")
    lines.append(f"- pass_count: `{kpis.get('pass_count', 0)}`")
    lines.append(f"- fail_count: `{kpis.get('fail_count', 0)}`")
    lines.append(f"- needs_review_count: `{kpis.get('needs_review_count', 0)}`")

    lines.extend(["", "## Risk-Level Counts", ""])
    risk_counts = summary.get("risk_level_counts", {})
    if risk_counts:
        for k in sorted(risk_counts.keys()):
            lines.append(f"- {k}: `{risk_counts[k]}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Review Volume (Last 7 Days)", ""])
    volume = kpis.get("review_volume_last_7_days", [])
    if volume:
        for item in volume:
            lines.append(f"- {item.get('date')}: `{item.get('count')}`")
    else:
        lines.append("- `none`")

    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _default_md_path(path: str) -> str:
    p = Path(path)
    if p.suffix == ".json":
        return str(p.with_suffix(".md"))
    return f"{path}.md"


def _parse_utc(value: str) -> datetime:
    txt = value.strip()
    if txt.endswith("Z"):
        txt = txt[:-1] + "+00:00"
    dt = datetime.fromisoformat(txt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize GateForge review ledger")
    parser.add_argument("--ledger", default="artifacts/review/ledger.jsonl", help="Ledger JSONL path")
    parser.add_argument(
        "--summary-out",
        default="artifacts/review/ledger_summary.json",
        help="Where to write summary JSON",
    )
    parser.add_argument("--report-out", default=None, help="Where to write summary markdown")
    parser.add_argument("--export-out", default=None, help="Optional path to write filtered records JSON")
    parser.add_argument("--proposal-id", default=None, help="Filter by proposal_id")
    parser.add_argument("--reviewer", default=None, help="Filter by reviewer")
    parser.add_argument("--final-status", default=None, help="Filter by final_status")
    parser.add_argument("--since-utc", default=None, help="Filter by recorded_at_utc >= value (ISO-8601)")
    parser.add_argument("--until-utc", default=None, help="Filter by recorded_at_utc <= value (ISO-8601)")
    args = parser.parse_args()

    rows = load_review_ledger(args.ledger)
    rows = filter_review_ledger(
        rows,
        proposal_id=args.proposal_id,
        reviewer=args.reviewer,
        final_status=args.final_status,
        since_utc=args.since_utc,
        until_utc=args.until_utc,
    )
    summary = summarize_review_ledger(rows)
    write_json(args.summary_out, summary)
    write_markdown(args.report_out or _default_md_path(args.summary_out), summary)
    if args.export_out:
        write_json(args.export_out, {"total_records": len(rows), "records": rows})
    print(json.dumps({"total_records": summary["total_records"]}))


if __name__ == "__main__":
    main()
