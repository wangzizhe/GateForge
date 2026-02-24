from __future__ import annotations

import argparse
import json
from collections import Counter
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
        "# GateForge Runtime Ledger History",
        "",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_total_records: `{payload.get('latest_total_records')}`",
        f"- latest_pass_rate: `{payload.get('latest_pass_rate')}`",
        f"- latest_fail_rate: `{payload.get('latest_fail_rate')}`",
        f"- latest_needs_review_rate: `{payload.get('latest_needs_review_rate')}`",
        f"- avg_pass_rate: `{payload.get('avg_pass_rate')}`",
        f"- avg_fail_rate: `{payload.get('avg_fail_rate')}`",
        "",
        "## Source Counts",
        "",
    ]
    for key, value in sorted((payload.get("source_counts") or {}).items()):
        lines.append(f"- {key}: `{value}`")
    if not (payload.get("source_counts") or {}):
        lines.append("- `none`")
    lines.extend(["", "## Alerts", ""])
    alerts = payload.get("alerts", [])
    if alerts:
        lines.extend([f"- `{a}`" for a in alerts])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append runtime ledger summaries into history and aggregate")
    parser.add_argument("--record", action="append", default=[], help="runtime_ledger summary JSON path")
    parser.add_argument("--ledger", default="artifacts/governance_runtime/history.jsonl")
    parser.add_argument("--out", default="artifacts/governance_runtime/history_summary.json")
    parser.add_argument("--report-out", default=None)
    parser.add_argument("--fail-rate-alert-threshold", type=float, default=0.3)
    parser.add_argument("--needs-review-alert-threshold", type=float, default=0.4)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    append_rows: list[dict] = []
    for path in args.record:
        payload = _load_json(path)
        kpis = payload.get("kpis", {}) if isinstance(payload.get("kpis"), dict) else {}
        append_rows.append(
            {
                "recorded_at_utc": now,
                "source_record_path": path,
                "total_records": int(payload.get("total_records", 0) or 0),
                "pass_rate": float(kpis.get("pass_rate", 0.0) or 0.0),
                "fail_rate": float(kpis.get("fail_rate", 0.0) or 0.0),
                "needs_review_rate": float(kpis.get("needs_review_rate", 0.0) or 0.0),
                "source_counts": payload.get("source_counts", {}),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}
    avg_pass_rate = round(sum(float(r.get("pass_rate", 0.0) or 0.0) for r in rows) / max(1, total), 4)
    avg_fail_rate = round(sum(float(r.get("fail_rate", 0.0) or 0.0) for r in rows) / max(1, total), 4)
    avg_needs_review_rate = round(sum(float(r.get("needs_review_rate", 0.0) or 0.0) for r in rows) / max(1, total), 4)
    source_counter = Counter()
    for row in rows:
        source_counts = row.get("source_counts")
        if not isinstance(source_counts, dict):
            continue
        for k, v in source_counts.items():
            if isinstance(k, str) and isinstance(v, (int, float)):
                source_counter[k] += int(v)

    alerts: list[str] = []
    if float(latest.get("fail_rate", 0.0) or 0.0) >= args.fail_rate_alert_threshold:
        alerts.append("latest_fail_rate_high")
    if float(latest.get("needs_review_rate", 0.0) or 0.0) >= args.needs_review_alert_threshold:
        alerts.append("latest_needs_review_rate_high")

    summary = {
        "generated_at_utc": now,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "latest_total_records": int(latest.get("total_records", 0) or 0),
        "latest_pass_rate": float(latest.get("pass_rate", 0.0) or 0.0),
        "latest_fail_rate": float(latest.get("fail_rate", 0.0) or 0.0),
        "latest_needs_review_rate": float(latest.get("needs_review_rate", 0.0) or 0.0),
        "avg_pass_rate": avg_pass_rate,
        "avg_fail_rate": avg_fail_rate,
        "avg_needs_review_rate": avg_needs_review_rate,
        "source_counts": dict(source_counter),
        "alerts": alerts,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"total_records": total, "alerts": alerts}))


if __name__ == "__main__":
    main()
