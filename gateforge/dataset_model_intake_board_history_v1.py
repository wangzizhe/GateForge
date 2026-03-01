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


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Model Intake Board History v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_status: `{payload.get('latest_status')}`",
        f"- avg_board_score: `{payload.get('avg_board_score')}`",
        f"- blocked_rate: `{payload.get('blocked_rate')}`",
        f"- ready_rate: `{payload.get('ready_rate')}`",
        f"- ingested_rate: `{payload.get('ingested_rate')}`",
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
    parser = argparse.ArgumentParser(description="Append model intake board summaries and emit history")
    parser.add_argument("--record", action="append", default=[], help="model intake board summary JSON path")
    parser.add_argument("--ledger", default="artifacts/dataset_model_intake_board_history_v1/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_model_intake_board_history_v1/summary.json")
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
                "board_score": round(_to_float(payload.get("board_score", 0.0)), 2),
                "total_candidates": _to_int(payload.get("total_candidates", 0)),
                "blocked_count": _to_int(payload.get("blocked_count", 0)),
                "ready_count": _to_int(payload.get("ready_count", 0)),
                "ingested_count": _to_int(payload.get("ingested_count", 0)),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}

    total_candidates = sum(_to_int(r.get("total_candidates", 0)) for r in rows)
    total_blocked = sum(_to_int(r.get("blocked_count", 0)) for r in rows)
    total_ready = sum(_to_int(r.get("ready_count", 0)) for r in rows)
    total_ingested = sum(_to_int(r.get("ingested_count", 0)) for r in rows)
    avg_score = round(sum(_to_float(r.get("board_score", 0.0)) for r in rows) / max(1, total), 4)

    blocked_rate = round(total_blocked / max(1, total_candidates), 4)
    ready_rate = round(total_ready / max(1, total_candidates), 4)
    ingested_rate = round(total_ingested / max(1, total_candidates), 4)

    alerts: list[str] = []
    if str(latest.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_board_not_pass")
    if blocked_rate > 0.35 and total >= 3:
        alerts.append("blocked_rate_high")
    if ingested_rate < 0.2 and total >= 3:
        alerts.append("ingested_rate_low")
    if avg_score < 75.0 and total >= 3:
        alerts.append("avg_board_score_low")

    status = "PASS" if not alerts else "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": now,
        "status": status,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "latest_status": latest.get("status"),
        "latest_board_score": latest.get("board_score"),
        "avg_board_score": avg_score,
        "blocked_rate": blocked_rate,
        "ready_rate": ready_rate,
        "ingested_rate": ingested_rate,
        "alerts": alerts,
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_records": total, "avg_board_score": avg_score}))


if __name__ == "__main__":
    main()
