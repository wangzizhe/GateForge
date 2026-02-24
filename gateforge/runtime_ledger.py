from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RUNTIME_LEDGER_SCHEMA_VERSION = "0.1.0"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_runtime_ledger(ledger_path: str, record: dict) -> None:
    p = Path(ledger_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")


def load_runtime_ledger(ledger_path: str) -> list[dict]:
    p = Path(ledger_path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        txt = line.strip()
        if not txt:
            continue
        rows.append(json.loads(txt))
    return rows


def build_runtime_record(summary: dict, *, source: str) -> dict:
    fail_reasons = summary.get("fail_reasons", [])
    if not isinstance(fail_reasons, list):
        fail_reasons = []
    policy_reasons = summary.get("policy_reasons", [])
    if not isinstance(policy_reasons, list):
        policy_reasons = []
    required_checks = summary.get("required_human_checks", [])
    if not isinstance(required_checks, list):
        required_checks = []

    status = summary.get("status")
    policy_decision = summary.get("policy_decision")
    if not isinstance(status, str):
        status = "UNKNOWN"
    if not isinstance(policy_decision, str):
        policy_decision = status

    return {
        "schema_version": RUNTIME_LEDGER_SCHEMA_VERSION,
        "recorded_at_utc": _now_utc(),
        "source": source,
        "proposal_id": summary.get("proposal_id"),
        "status": status,
        "policy_decision": policy_decision,
        "risk_level": summary.get("risk_level"),
        "policy_profile": summary.get("policy_profile"),
        "policy_version": summary.get("policy_version"),
        "planner_backend": summary.get("planner_backend"),
        "fail_reasons": fail_reasons,
        "policy_reasons": policy_reasons,
        "required_human_checks_count": len(required_checks),
    }


def summarize_runtime_ledger(rows: list[dict]) -> dict:
    status_counts = Counter()
    source_counts = Counter()
    policy_decision_counts = Counter()
    risk_counts = Counter()
    profile_counts = Counter()
    fail_reason_counts = Counter()
    policy_reason_counts = Counter()

    for row in rows:
        status = row.get("status")
        source = row.get("source")
        policy_decision = row.get("policy_decision")
        risk = row.get("risk_level")
        profile = row.get("policy_profile")

        if isinstance(status, str):
            status_counts[status] += 1
        if isinstance(source, str):
            source_counts[source] += 1
        if isinstance(policy_decision, str):
            policy_decision_counts[policy_decision] += 1
        if isinstance(risk, str):
            risk_counts[risk] += 1
        if isinstance(profile, str):
            profile_counts[profile] += 1

        for reason in row.get("fail_reasons", []) or []:
            if isinstance(reason, str):
                fail_reason_counts[reason.split(":", 1)[0]] += 1
        for reason in row.get("policy_reasons", []) or []:
            if isinstance(reason, str):
                policy_reason_counts[reason.split(":", 1)[0]] += 1

    total = len(rows)
    pass_count = int(status_counts.get("PASS", 0))
    fail_count = int(status_counts.get("FAIL", 0))
    needs_review_count = int(status_counts.get("NEEDS_REVIEW", 0))
    return {
        "generated_at_utc": _now_utc(),
        "total_records": total,
        "status_counts": dict(status_counts),
        "source_counts": dict(source_counts),
        "policy_decision_counts": dict(policy_decision_counts),
        "risk_level_counts": dict(risk_counts),
        "policy_profile_counts": dict(profile_counts),
        "top_fail_reasons": [
            {"reason": reason, "count": count}
            for reason, count in fail_reason_counts.most_common(10)
        ],
        "top_policy_reasons": [
            {"reason": reason, "count": count}
            for reason, count in policy_reason_counts.most_common(10)
        ],
        "kpis": {
            "pass_rate": round(pass_count / total, 4) if total else 0.0,
            "fail_rate": round(fail_count / total, 4) if total else 0.0,
            "needs_review_rate": round(needs_review_count / total, 4) if total else 0.0,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "needs_review_count": needs_review_count,
        },
    }


def write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Runtime Ledger Summary",
        "",
        f"- generated_at_utc: `{summary.get('generated_at_utc')}`",
        f"- total_records: `{summary.get('total_records')}`",
        f"- pass_rate: `{summary.get('kpis', {}).get('pass_rate')}`",
        f"- fail_rate: `{summary.get('kpis', {}).get('fail_rate')}`",
        f"- needs_review_rate: `{summary.get('kpis', {}).get('needs_review_rate')}`",
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
    lines.extend(["", "## Source Counts", ""])
    source_counts = summary.get("source_counts", {})
    if source_counts:
        for k in sorted(source_counts.keys()):
            lines.append(f"- {k}: `{source_counts[k]}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Top Fail Reasons", ""])
    top_fail = summary.get("top_fail_reasons", [])
    if top_fail:
        for item in top_fail:
            lines.append(f"- {item.get('reason')}: `{item.get('count')}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Top Policy Reasons", ""])
    top_policy = summary.get("top_policy_reasons", [])
    if top_policy:
        for item in top_policy:
            lines.append(f"- {item.get('reason')}: `{item.get('count')}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="GateForge runtime ledger append + summary")
    parser.add_argument(
        "--ledger",
        default="artifacts/governance_runtime/decision_ledger.jsonl",
        help="Runtime decision ledger JSONL path",
    )
    parser.add_argument("--append-summary", default=None, help="Optional run/autopilot summary JSON to append")
    parser.add_argument(
        "--source",
        default="run",
        choices=["run", "autopilot"],
        help="Source label used when appending summary",
    )
    parser.add_argument(
        "--summary-out",
        default="artifacts/governance_runtime/ledger_summary.json",
        help="Where to write summarized ledger JSON",
    )
    parser.add_argument(
        "--report-out",
        default=None,
        help="Where to write summarized ledger markdown",
    )
    args = parser.parse_args()

    if args.append_summary:
        summary_payload = json.loads(Path(args.append_summary).read_text(encoding="utf-8"))
        append_runtime_ledger(args.ledger, build_runtime_record(summary_payload, source=args.source))

    rows = load_runtime_ledger(args.ledger)
    summary = summarize_runtime_ledger(rows)
    write_json(args.summary_out, summary)
    write_markdown(args.report_out or _default_md_path(args.summary_out), summary)
    print(json.dumps({"total_records": summary.get("total_records"), "ledger": args.ledger}))


if __name__ == "__main__":
    main()
