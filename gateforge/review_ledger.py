from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
import statistics


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


def summarize_review_ledger(rows: list[dict], sla_seconds: float = 86400.0) -> dict:
    status_counter = Counter()
    reviewer_counter = Counter()
    reason_counter = Counter()
    risk_counter = Counter()
    risk_status_counter: dict[str, Counter] = {}
    guardrail_decision_counter = Counter()
    guardrail_rule_counter = Counter()
    date_counter = Counter()
    last24h_status_counter = Counter()
    last7d_status_counter = Counter()
    now_utc = datetime.now(timezone.utc)
    cutoff_24h = now_utc - timedelta(hours=24)
    cutoff_7d = now_utc - timedelta(days=7)
    resolution_values: list[float] = []
    proposal_stats: dict[str, dict] = {}
    for row in rows:
        status = row.get("final_status")
        reviewer = row.get("reviewer")
        risk = row.get("risk_level")
        recorded_at = row.get("recorded_at_utc")
        proposal_id = row.get("proposal_id")
        if isinstance(proposal_id, str) and proposal_id.strip():
            item = proposal_stats.setdefault(
                proposal_id,
                {"proposal_id": proposal_id, "total": 0, "fail": 0, "needs_review": 0, "pass": 0, "last_status": None},
            )
            item["total"] += 1
            if status == "FAIL":
                item["fail"] += 1
            elif status == "NEEDS_REVIEW":
                item["needs_review"] += 1
            elif status == "PASS":
                item["pass"] += 1
            item["last_status"] = status
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
                recorded_dt = _parse_utc(recorded_at)
                date_key = recorded_dt.date().isoformat()
                date_counter[date_key] += 1
                if isinstance(status, str):
                    if recorded_dt >= cutoff_24h:
                        last24h_status_counter[status] += 1
                    if recorded_dt >= cutoff_7d:
                        last7d_status_counter[status] += 1
            except Exception:
                pass
        gd = row.get("planner_guardrail_decision")
        if isinstance(gd, str) and gd.strip():
            guardrail_decision_counter[gd] += 1
        for rid in row.get("planner_guardrail_rule_ids", []) or []:
            if isinstance(rid, str) and rid.strip():
                guardrail_rule_counter[rid] += 1
        res = row.get("resolution_seconds")
        if isinstance(res, (int, float)) and float(res) >= 0:
            resolution_values.append(float(res))
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
    avg_resolution = round(sum(resolution_values) / len(resolution_values), 3) if resolution_values else None
    p50_resolution = round(statistics.median(resolution_values), 3) if resolution_values else None
    if resolution_values:
        sorted_res = sorted(resolution_values)
        idx = max(0, min(len(sorted_res) - 1, int(0.95 * (len(sorted_res) - 1))))
        p95_resolution = round(sorted_res[idx], 3)
    else:
        p95_resolution = None
    breach_count = 0
    if resolution_values:
        breach_count = sum(1 for v in resolution_values if v > float(sla_seconds))
    breach_rate = round(breach_count / len(resolution_values), 4) if resolution_values else 0.0
    guardrail_total = sum(guardrail_decision_counter.values())
    guardrail_fail_count = int(guardrail_decision_counter.get("FAIL", 0))
    guardrail_fail_rate = round(guardrail_fail_count / guardrail_total, 4) if guardrail_total else 0.0
    total_last_24h = sum(last24h_status_counter.values())
    total_last_7d = sum(last7d_status_counter.values())
    approval_rate_last_24h = (
        round(last24h_status_counter.get("PASS", 0) / total_last_24h, 4) if total_last_24h else 0.0
    )
    approval_rate_last_7d = (
        round(last7d_status_counter.get("PASS", 0) / total_last_7d, 4) if total_last_7d else 0.0
    )
    unstable = []
    for item in proposal_stats.values():
        non_pass = int(item["fail"]) + int(item["needs_review"])
        unstable.append(
            {
                "proposal_id": item["proposal_id"],
                "non_pass_count": non_pass,
                "fail_count": int(item["fail"]),
                "needs_review_count": int(item["needs_review"]),
                "pass_count": int(item["pass"]),
                "total_count": int(item["total"]),
                "last_status": item["last_status"],
            }
        )
    unstable.sort(
        key=lambda x: (x["non_pass_count"], x["fail_count"], x["needs_review_count"], -x["pass_count"]),
        reverse=True,
    )
    top_unstable = unstable[:5]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_records": len(rows),
        "status_counts": dict(status_counter),
        "reviewer_counts": dict(reviewer_counter),
        "reason_prefix_counts": dict(reason_counter),
        "risk_level_counts": dict(risk_counter),
        "planner_guardrail_decision_counts": dict(guardrail_decision_counter),
        "planner_guardrail_rule_id_counts": dict(guardrail_rule_counter),
        "top_unstable_proposals": top_unstable,
        "kpis": {
            "approval_rate": approval_rate,
            "fail_rate": fail_rate,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "needs_review_count": needs_review_count,
            "by_risk_status_counts": by_risk,
            "review_volume_last_7_days": volume_by_day,
            "avg_resolution_seconds": avg_resolution,
            "p50_resolution_seconds": p50_resolution,
            "p95_resolution_seconds": p95_resolution,
            "sla_seconds": float(sla_seconds),
            "sla_breach_count": int(breach_count),
            "sla_breach_rate": breach_rate,
            "guardrail_record_count": int(guardrail_total),
            "guardrail_fail_count": int(guardrail_fail_count),
            "guardrail_fail_rate": guardrail_fail_rate,
            "review_volume_last_24h": int(total_last_24h),
            "review_volume_last_7d": int(total_last_7d),
            "approval_rate_last_24h": approval_rate_last_24h,
            "approval_rate_last_7d": approval_rate_last_7d,
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
    lines.append(f"- avg_resolution_seconds: `{kpis.get('avg_resolution_seconds')}`")
    lines.append(f"- p50_resolution_seconds: `{kpis.get('p50_resolution_seconds')}`")
    lines.append(f"- p95_resolution_seconds: `{kpis.get('p95_resolution_seconds')}`")
    lines.append(f"- sla_seconds: `{kpis.get('sla_seconds')}`")
    lines.append(f"- sla_breach_count: `{kpis.get('sla_breach_count', 0)}`")
    lines.append(f"- sla_breach_rate: `{kpis.get('sla_breach_rate', 0.0)}`")
    lines.append(f"- guardrail_record_count: `{kpis.get('guardrail_record_count', 0)}`")
    lines.append(f"- guardrail_fail_count: `{kpis.get('guardrail_fail_count', 0)}`")
    lines.append(f"- guardrail_fail_rate: `{kpis.get('guardrail_fail_rate', 0.0)}`")
    lines.append(f"- review_volume_last_24h: `{kpis.get('review_volume_last_24h', 0)}`")
    lines.append(f"- review_volume_last_7d: `{kpis.get('review_volume_last_7d', 0)}`")
    lines.append(f"- approval_rate_last_24h: `{kpis.get('approval_rate_last_24h', 0.0)}`")
    lines.append(f"- approval_rate_last_7d: `{kpis.get('approval_rate_last_7d', 0.0)}`")

    lines.extend(["", "## Risk-Level Counts", ""])
    risk_counts = summary.get("risk_level_counts", {})
    if risk_counts:
        for k in sorted(risk_counts.keys()):
            lines.append(f"- {k}: `{risk_counts[k]}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Planner Guardrail Decision Counts", ""])
    guardrail_decisions = summary.get("planner_guardrail_decision_counts", {})
    if guardrail_decisions:
        for k in sorted(guardrail_decisions.keys()):
            lines.append(f"- {k}: `{guardrail_decisions[k]}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Planner Guardrail Rule IDs", ""])
    guardrail_rules = summary.get("planner_guardrail_rule_id_counts", {})
    if guardrail_rules:
        for k in sorted(guardrail_rules.keys()):
            lines.append(f"- {k}: `{guardrail_rules[k]}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Top Unstable Proposals", ""])
    unstable = summary.get("top_unstable_proposals", [])
    if unstable:
        for item in unstable:
            lines.append(
                f"- {item.get('proposal_id')}: non_pass=`{item.get('non_pass_count')}` "
                f"fail=`{item.get('fail_count')}` needs_review=`{item.get('needs_review_count')}` "
                f"pass=`{item.get('pass_count')}` last_status=`{item.get('last_status')}`"
            )
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
    parser.add_argument("--sla-seconds", type=float, default=86400.0, help="SLA threshold in seconds")
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
    summary = summarize_review_ledger(rows, sla_seconds=args.sla_seconds)
    write_json(args.summary_out, summary)
    write_markdown(args.report_out or _default_md_path(args.summary_out), summary)
    if args.export_out:
        write_json(args.export_out, {"total_records": len(rows), "records": rows})
    print(json.dumps({"total_records": summary["total_records"]}))


if __name__ == "__main__":
    main()
