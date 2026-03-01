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
        "# GateForge Anchor Model Pack History v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_status: `{payload.get('latest_status')}`",
        f"- avg_pack_quality_score: `{payload.get('avg_pack_quality_score')}`",
        f"- avg_selected_cases: `{payload.get('avg_selected_cases')}`",
        f"- avg_selected_large_cases: `{payload.get('avg_selected_large_cases')}`",
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
    parser = argparse.ArgumentParser(description="Append anchor model pack summaries and emit history")
    parser.add_argument("--record", action="append", default=[], help="anchor model pack summary JSON path")
    parser.add_argument("--ledger", default="artifacts/dataset_anchor_model_pack_history_v1/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_anchor_model_pack_history_v1/summary.json")
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
                "pack_quality_score": round(_to_float(payload.get("pack_quality_score", 0.0)), 2),
                "selected_cases": _to_int(payload.get("selected_cases", 0)),
                "selected_large_cases": _to_int(payload.get("selected_large_cases", 0)),
                "unique_failure_types": _to_int(payload.get("unique_failure_types", 0)),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}

    avg_quality = round(sum(_to_float(r.get("pack_quality_score", 0.0)) for r in rows) / max(1, total), 4)
    avg_cases = round(sum(_to_float(r.get("selected_cases", 0.0)) for r in rows) / max(1, total), 4)
    avg_large = round(sum(_to_float(r.get("selected_large_cases", 0.0)) for r in rows) / max(1, total), 4)
    avg_failure_types = round(sum(_to_float(r.get("unique_failure_types", 0.0)) for r in rows) / max(1, total), 4)

    alerts: list[str] = []
    if str(latest.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_pack_not_pass")
    if avg_quality < 78.0 and total >= 3:
        alerts.append("avg_pack_quality_score_low")
    if avg_large < 2.0 and total >= 3:
        alerts.append("avg_selected_large_cases_low")
    if avg_failure_types < 4.0 and total >= 3:
        alerts.append("avg_failure_type_diversity_low")

    status = "PASS" if not alerts else "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": now,
        "status": status,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "latest_status": latest.get("status"),
        "latest_pack_quality_score": latest.get("pack_quality_score"),
        "avg_pack_quality_score": avg_quality,
        "avg_selected_cases": avg_cases,
        "avg_selected_large_cases": avg_large,
        "avg_unique_failure_types": avg_failure_types,
        "alerts": alerts,
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_records": total, "avg_pack_quality_score": avg_quality}))


if __name__ == "__main__":
    main()
