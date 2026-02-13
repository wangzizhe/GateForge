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
    for row in rows:
        status = row.get("final_status")
        reviewer = row.get("reviewer")
        if isinstance(status, str):
            status_counter[status] += 1
        if isinstance(reviewer, str) and reviewer.strip():
            reviewer_counter[reviewer] += 1
        for reason in row.get("final_reasons", []) or []:
            if isinstance(reason, str):
                prefix = reason.split(":", 1)[0]
                reason_counter[prefix] += 1
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_records": len(rows),
        "status_counts": dict(status_counter),
        "reviewer_counts": dict(reviewer_counter),
        "reason_prefix_counts": dict(reason_counter),
    }


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

    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _default_md_path(path: str) -> str:
    p = Path(path)
    if p.suffix == ".json":
        return str(p.with_suffix(".md"))
    return f"{path}.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize GateForge review ledger")
    parser.add_argument("--ledger", default="artifacts/review/ledger.jsonl", help="Ledger JSONL path")
    parser.add_argument(
        "--summary-out",
        default="artifacts/review/ledger_summary.json",
        help="Where to write summary JSON",
    )
    parser.add_argument("--report-out", default=None, help="Where to write summary markdown")
    args = parser.parse_args()

    rows = load_review_ledger(args.ledger)
    summary = summarize_review_ledger(rows)
    write_json(args.summary_out, summary)
    write_markdown(args.report_out or _default_md_path(args.summary_out), summary)
    print(json.dumps({"total_records": summary["total_records"]}))


if __name__ == "__main__":
    main()
