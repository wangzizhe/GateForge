from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _load_rows(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    rows.sort(key=lambda x: str(x.get("recorded_at_utc") or ""))
    return rows


def _match_row(
    row: dict,
    *,
    decision: str | None,
    mismatch_code: str | None,
    since_utc: str | None,
    until_utc: str | None,
) -> bool:
    ts = str(row.get("recorded_at_utc") or "")
    if since_utc and ts and ts < since_utc:
        return False
    if until_utc and ts and ts > until_utc:
        return False
    if decision:
        if str(row.get("decision") or "").upper() != decision.upper():
            return False
    if mismatch_code:
        mismatches = row.get("mismatches", [])
        if not isinstance(mismatches, list):
            return False
        code_set = {str(item.get("code")) for item in mismatches if isinstance(item, dict)}
        if mismatch_code not in code_set:
            return False
    return True


def _summarize(rows: list[dict]) -> dict:
    decision_counts = Counter()
    mismatch_codes = Counter()
    for row in rows:
        decision_counts[str(row.get("decision") or "UNKNOWN").upper()] += 1
        mismatches = row.get("mismatches", [])
        if not isinstance(mismatches, list):
            continue
        for item in mismatches:
            if isinstance(item, dict) and isinstance(item.get("code"), str):
                mismatch_codes[str(item["code"])] += 1
    return {
        "total_rows": len(rows),
        "decision_counts": dict(decision_counts),
        "mismatch_code_counts": dict(mismatch_codes),
        "latest_recorded_at_utc": rows[-1].get("recorded_at_utc") if rows else None,
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Governance Replay Query",
        "",
        f"- total_rows: `{summary.get('total_rows')}`",
        f"- latest_recorded_at_utc: `{summary.get('latest_recorded_at_utc')}`",
        "",
        "## Decision Counts",
        "",
    ]
    decisions = summary.get("decision_counts", {})
    if decisions:
        for key in sorted(decisions.keys()):
            lines.append(f"- {key}: `{decisions[key]}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Mismatch Code Counts", ""])
    mismatch_codes = summary.get("mismatch_code_counts", {})
    if mismatch_codes:
        for key in sorted(mismatch_codes.keys()):
            lines.append(f"- {key}: `{mismatch_codes[key]}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter/query governance replay ledger")
    parser.add_argument("--ledger", required=True, help="Replay ledger JSONL path")
    parser.add_argument("--decision", default=None, help="Filter by replay decision")
    parser.add_argument("--mismatch-code", default=None, help="Filter rows containing mismatch code")
    parser.add_argument("--since-utc", default=None, help="Filter rows recorded_at_utc >= this timestamp")
    parser.add_argument("--until-utc", default=None, help="Filter rows recorded_at_utc <= this timestamp")
    parser.add_argument("--export-out", default=None, help="Optional matched rows output JSON path")
    parser.add_argument("--out", default="artifacts/governance_replay/query_summary.json", help="Summary output JSON path")
    parser.add_argument("--report", default=None, help="Summary markdown path")
    args = parser.parse_args()

    rows = _load_rows(args.ledger)
    matched = [
        row
        for row in rows
        if _match_row(
            row,
            decision=args.decision,
            mismatch_code=args.mismatch_code,
            since_utc=args.since_utc,
            until_utc=args.until_utc,
        )
    ]
    summary = {
        **_summarize(matched),
        "filters": {
            "decision": args.decision,
            "mismatch_code": args.mismatch_code,
            "since_utc": args.since_utc,
            "until_utc": args.until_utc,
        },
    }
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    if args.export_out:
        _write_json(args.export_out, {"rows": matched})
    print(json.dumps({"total_rows": summary["total_rows"]}))


if __name__ == "__main__":
    main()
