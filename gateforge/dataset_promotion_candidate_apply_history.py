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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Dataset Promotion Candidate Apply History",
        "",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_final_status: `{payload.get('latest_final_status')}`",
        f"- pass_rate: `{payload.get('pass_rate')}`",
        f"- needs_review_rate: `{payload.get('needs_review_rate')}`",
        f"- fail_rate: `{payload.get('fail_rate')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = payload.get("alerts", [])
    if isinstance(alerts, list) and alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append dataset promotion apply summaries and emit aggregated history")
    parser.add_argument("--record", action="append", default=[], help="dataset promotion apply summary JSON path")
    parser.add_argument("--ledger", default="artifacts/dataset_promotion_candidate_apply_history/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_promotion_candidate_apply_history/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    append_rows: list[dict] = []
    for path in args.record:
        payload = _load_json(path)
        append_rows.append(
            {
                "recorded_at_utc": now,
                "source_record_path": path,
                "final_status": str(payload.get("final_status") or "UNKNOWN"),
                "apply_action": str(payload.get("apply_action") or "unknown"),
                "decision": str(payload.get("decision") or ""),
                "confidence": payload.get("confidence"),
                "reasons_count": len(payload.get("reasons") or []),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    status_counts = {"PASS": 0, "NEEDS_REVIEW": 0, "FAIL": 0, "UNKNOWN": 0}
    for row in rows:
        status = str(row.get("final_status") or "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
    latest = rows[-1] if rows else {}
    pass_rate = round(status_counts.get("PASS", 0) / max(1, total), 4)
    needs_review_rate = round(status_counts.get("NEEDS_REVIEW", 0) / max(1, total), 4)
    fail_rate = round(status_counts.get("FAIL", 0) / max(1, total), 4)

    alerts: list[str] = []
    if str(latest.get("final_status") or "") == "FAIL":
        alerts.append("latest_apply_fail")
    if fail_rate >= 0.3 and total >= 3:
        alerts.append("apply_fail_rate_high")
    if needs_review_rate >= 0.4 and total >= 3:
        alerts.append("apply_needs_review_rate_high")

    summary = {
        "generated_at_utc": now,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "status_counts": status_counts,
        "latest_final_status": latest.get("final_status"),
        "latest_apply_action": latest.get("apply_action"),
        "pass_rate": pass_rate,
        "needs_review_rate": needs_review_rate,
        "fail_rate": fail_rate,
        "alerts": alerts,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"total_records": total, "fail_rate": fail_rate, "needs_review_rate": needs_review_rate}))


if __name__ == "__main__":
    main()
