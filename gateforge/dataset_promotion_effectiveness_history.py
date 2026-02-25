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
        "# GateForge Dataset Promotion Effectiveness History",
        "",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_decision: `{payload.get('latest_decision')}`",
        f"- keep_rate: `{payload.get('keep_rate')}`",
        f"- needs_review_rate: `{payload.get('needs_review_rate')}`",
        f"- rollback_review_rate: `{payload.get('rollback_review_rate')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = payload.get("alerts", [])
    if isinstance(alerts, list) and alerts:
        for a in alerts:
            lines.append(f"- `{a}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append dataset promotion effectiveness summaries and emit history")
    parser.add_argument("--record", action="append", default=[], help="dataset promotion effectiveness summary JSON path")
    parser.add_argument("--ledger", default="artifacts/dataset_promotion_effectiveness_history/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_promotion_effectiveness_history/summary.json")
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
                "decision": str(payload.get("decision") or "UNKNOWN"),
                "reasons_count": len(payload.get("reasons") or []),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    decision_counts = {"KEEP": 0, "NEEDS_REVIEW": 0, "ROLLBACK_REVIEW": 0, "UNKNOWN": 0}
    for row in rows:
        decision = str(row.get("decision") or "UNKNOWN")
        decision_counts[decision] = decision_counts.get(decision, 0) + 1

    latest = rows[-1] if rows else {}
    keep_rate = round(decision_counts.get("KEEP", 0) / max(1, total), 4)
    needs_review_rate = round(decision_counts.get("NEEDS_REVIEW", 0) / max(1, total), 4)
    rollback_rate = round(decision_counts.get("ROLLBACK_REVIEW", 0) / max(1, total), 4)

    alerts: list[str] = []
    if str(latest.get("decision") or "") == "ROLLBACK_REVIEW":
        alerts.append("latest_rollback_review")
    if rollback_rate >= 0.3 and total >= 3:
        alerts.append("rollback_review_rate_high")
    if needs_review_rate >= 0.5 and total >= 3:
        alerts.append("needs_review_rate_high")

    summary = {
        "generated_at_utc": now,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "decision_counts": decision_counts,
        "latest_decision": latest.get("decision"),
        "keep_rate": keep_rate,
        "needs_review_rate": needs_review_rate,
        "rollback_review_rate": rollback_rate,
        "alerts": alerts,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"total_records": total, "latest_decision": latest.get("decision"), "rollback_review_rate": rollback_rate}))


if __name__ == "__main__":
    main()
