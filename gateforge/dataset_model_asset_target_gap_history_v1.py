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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Model Asset Target Gap History v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_status: `{payload.get('latest_status')}`",
        f"- avg_target_gap_score: `{payload.get('avg_target_gap_score')}`",
        f"- avg_critical_gap_count: `{payload.get('avg_critical_gap_count')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
    if alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append model asset target gap summaries and emit history")
    parser.add_argument("--record", action="append", default=[])
    parser.add_argument("--ledger", default="artifacts/dataset_model_asset_target_gap_history_v1/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_model_asset_target_gap_history_v1/summary.json")
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
                "status": str(payload.get("status") or "UNKNOWN"),
                "target_gap_score": round(_to_float(payload.get("target_gap_score", 0.0)), 4),
                "critical_gap_count": round(_to_float(payload.get("critical_gap_count", 0.0)), 4),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}

    avg_target_gap_score = round(sum(_to_float(r.get("target_gap_score", 0.0)) for r in rows) / max(1, total), 4)
    avg_critical_gap_count = round(sum(_to_float(r.get("critical_gap_count", 0.0)) for r in rows) / max(1, total), 4)

    alerts: list[str] = []
    if str(latest.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_target_gap_not_pass")
    if avg_target_gap_score > 25.0 and total >= 3:
        alerts.append("avg_target_gap_score_high")
    if avg_critical_gap_count >= 1.0 and total >= 3:
        alerts.append("avg_critical_gap_count_non_zero")

    status = "PASS" if not alerts else "NEEDS_REVIEW"

    out = {
        "generated_at_utc": now,
        "status": status,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "latest_status": latest.get("status"),
        "latest_target_gap_score": latest.get("target_gap_score"),
        "latest_critical_gap_count": latest.get("critical_gap_count"),
        "avg_target_gap_score": avg_target_gap_score,
        "avg_critical_gap_count": avg_critical_gap_count,
        "alerts": alerts,
    }

    _write_json(args.out, out)
    _write_markdown(args.report_out or _default_md_path(args.out), out)
    print(json.dumps({"status": status, "total_records": total, "avg_target_gap_score": avg_target_gap_score}))


if __name__ == "__main__":
    main()
