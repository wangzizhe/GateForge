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
        "# GateForge Dataset Promotion Candidate History",
        "",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_decision: `{payload.get('latest_decision')}`",
        f"- promote_rate: `{payload.get('promote_rate')}`",
        f"- hold_rate: `{payload.get('hold_rate')}`",
        f"- block_rate: `{payload.get('block_rate')}`",
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
    parser = argparse.ArgumentParser(description="Append dataset promotion candidate advisor outputs and summarize")
    parser.add_argument("--record", action="append", default=[], help="dataset promotion advisor JSON path")
    parser.add_argument("--ledger", default="artifacts/dataset_promotion_candidate_history/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_promotion_candidate_history/summary.json")
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
                "decision": str(advice.get("decision") or "UNKNOWN"),
                "action": str(advice.get("action") or "unknown"),
                "confidence": advice.get("confidence"),
                "reasons_count": len(advice.get("reasons") or []),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    decision_counts = {"PROMOTE": 0, "HOLD": 0, "BLOCK": 0, "UNKNOWN": 0}
    for row in rows:
        decision = str(row.get("decision") or "UNKNOWN")
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
    latest = rows[-1] if rows else {}
    promote_rate = round(decision_counts.get("PROMOTE", 0) / max(1, total), 4)
    hold_rate = round(decision_counts.get("HOLD", 0) / max(1, total), 4)
    block_rate = round(decision_counts.get("BLOCK", 0) / max(1, total), 4)

    alerts: list[str] = []
    if str(latest.get("decision") or "") == "BLOCK":
        alerts.append("latest_decision_block")
    if block_rate >= 0.3 and total >= 3:
        alerts.append("block_rate_high")
    if hold_rate >= 0.5 and total >= 3:
        alerts.append("hold_rate_high")

    summary = {
        "generated_at_utc": now,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "decision_counts": decision_counts,
        "latest_decision": latest.get("decision"),
        "latest_action": latest.get("action"),
        "promote_rate": promote_rate,
        "hold_rate": hold_rate,
        "block_rate": block_rate,
        "alerts": alerts,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"total_records": total, "promote_rate": promote_rate, "block_rate": block_rate}))


if __name__ == "__main__":
    main()
