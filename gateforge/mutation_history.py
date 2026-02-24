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
        "# GateForge Mutation History",
        "",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_pack_id: `{payload.get('latest_pack_id')}`",
        f"- latest_match_rate: `{payload.get('latest_match_rate')}`",
        f"- avg_match_rate: `{payload.get('avg_match_rate')}`",
        f"- latest_gate_pass_rate: `{payload.get('latest_gate_pass_rate')}`",
        f"- avg_gate_pass_rate: `{payload.get('avg_gate_pass_rate')}`",
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
    parser = argparse.ArgumentParser(description="Append mutation metrics to history ledger and summarize")
    parser.add_argument("--record", action="append", default=[], help="Mutation metrics JSON path (repeatable)")
    parser.add_argument("--ledger", default="artifacts/mutation_history/history.jsonl", help="History JSONL path")
    parser.add_argument("--out", default="artifacts/mutation_history/summary.json", help="History summary JSON path")
    parser.add_argument("--report-out", default=None, help="History summary markdown path")
    parser.add_argument("--min-match-rate", type=float, default=0.95, help="Alert threshold for latest match rate")
    parser.add_argument("--min-gate-pass-rate", type=float, default=0.95, help="Alert threshold for latest gate pass rate")
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
                "pack_id": payload.get("pack_id"),
                "pack_version": payload.get("pack_version"),
                "total_cases": int(payload.get("total_cases", 0) or 0),
                "match_rate": float(payload.get("expected_vs_actual_match_rate", 0.0) or 0.0),
                "gate_pass_rate": float(payload.get("gate_pass_rate", 0.0) or 0.0),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}
    avg_match_rate = round(sum(float(r.get("match_rate", 0.0) or 0.0) for r in rows) / max(1, total), 4)
    avg_gate_pass_rate = round(sum(float(r.get("gate_pass_rate", 0.0) or 0.0) for r in rows) / max(1, total), 4)
    alerts: list[str] = []
    if float(latest.get("match_rate", 0.0) or 0.0) < args.min_match_rate:
        alerts.append("latest_match_rate_low")
    if float(latest.get("gate_pass_rate", 0.0) or 0.0) < args.min_gate_pass_rate:
        alerts.append("latest_gate_pass_rate_low")

    summary = {
        "generated_at_utc": now,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "latest_pack_id": latest.get("pack_id"),
        "latest_pack_version": latest.get("pack_version"),
        "latest_match_rate": float(latest.get("match_rate", 0.0) or 0.0),
        "latest_gate_pass_rate": float(latest.get("gate_pass_rate", 0.0) or 0.0),
        "avg_match_rate": avg_match_rate,
        "avg_gate_pass_rate": avg_gate_pass_rate,
        "alerts": alerts,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"total_records": total, "latest_match_rate": summary["latest_match_rate"], "alerts": alerts}))


if __name__ == "__main__":
    main()
