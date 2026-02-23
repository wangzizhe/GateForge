from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        rows.append(json.loads(s))
    return rows


def _append_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True))
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
        "# GateForge Medium Benchmark History",
        "",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_pack_id: `{payload.get('latest_pack_id')}`",
        f"- latest_pass_rate: `{payload.get('latest_pass_rate')}`",
        f"- avg_pass_rate: `{payload.get('avg_pass_rate')}`",
        f"- latest_mismatch_case_count: `{payload.get('latest_mismatch_case_count')}`",
        f"- mismatch_case_total: `{payload.get('mismatch_case_total')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = payload.get("alerts", [])
    if isinstance(alerts, list) and alerts:
        for a in alerts:
            lines.append(f"- {a}")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append medium benchmark summaries to history ledger and aggregate KPIs")
    parser.add_argument("--record", action="append", default=[], help="Path to medium_benchmark summary JSON (repeatable)")
    parser.add_argument(
        "--ledger",
        default="artifacts/benchmark_medium_v1/history.jsonl",
        help="History ledger JSONL path",
    )
    parser.add_argument(
        "--out",
        default="artifacts/benchmark_medium_v1/history_summary.json",
        help="History summary JSON path",
    )
    parser.add_argument("--report-out", default=None, help="History summary markdown path")
    parser.add_argument("--min-pass-rate", type=float, default=0.9, help="Alert threshold for latest pass rate")
    parser.add_argument("--mismatch-threshold", type=int, default=1, help="Alert threshold for total mismatch cases")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    append_rows: list[dict] = []
    for record_path in args.record:
        payload = _load_json(record_path)
        append_rows.append(
            {
                "recorded_at_utc": now,
                "source_record_path": record_path,
                "pack_id": payload.get("pack_id"),
                "total_cases": int(payload.get("total_cases", 0) or 0),
                "pass_count": int(payload.get("pass_count", 0) or 0),
                "fail_count": int(payload.get("fail_count", 0) or 0),
                "pass_rate": float(payload.get("pass_rate", 0.0) or 0.0),
                "mismatch_case_count": int(payload.get("mismatch_case_count", 0) or 0),
            }
        )
    if append_rows:
        _append_rows(ledger_path, append_rows)

    rows = _load_ledger(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}
    avg_pass_rate = round(sum(float(r.get("pass_rate", 0.0) or 0.0) for r in rows) / total, 4) if total else 0.0
    mismatch_case_total = sum(int(r.get("mismatch_case_count", 0) or 0) for r in rows)
    fail_total = sum(int(r.get("fail_count", 0) or 0) for r in rows)
    pack_counter = Counter(str(r.get("pack_id") or "") for r in rows if r.get("pack_id"))
    alerts: list[str] = []
    if float(latest.get("pass_rate", 0.0) or 0.0) < args.min_pass_rate:
        alerts.append("latest_pass_rate_low")
    if mismatch_case_total >= max(1, int(args.mismatch_threshold)):
        alerts.append("mismatch_case_volume_high")
    if fail_total > 0:
        alerts.append("historical_fail_detected")

    summary = {
        "generated_at_utc": now,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "pack_id_counts": dict(pack_counter),
        "latest_pack_id": latest.get("pack_id"),
        "latest_pass_rate": float(latest.get("pass_rate", 0.0) or 0.0),
        "avg_pass_rate": avg_pass_rate,
        "latest_mismatch_case_count": int(latest.get("mismatch_case_count", 0) or 0),
        "mismatch_case_total": mismatch_case_total,
        "alerts": alerts,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"total_records": total, "latest_pass_rate": summary["latest_pass_rate"], "alerts": alerts}))


if __name__ == "__main__":
    main()
