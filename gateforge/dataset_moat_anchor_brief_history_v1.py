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
        "# GateForge Moat Anchor Brief History v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_recommendation: `{payload.get('latest_recommendation')}`",
        f"- avg_anchor_brief_score: `{payload.get('avg_anchor_brief_score')}`",
        f"- publish_rate: `{payload.get('publish_rate')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append moat anchor brief summaries and emit history")
    parser.add_argument("--record", action="append", default=[])
    parser.add_argument("--ledger", default="artifacts/dataset_moat_anchor_brief_history_v1/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_moat_anchor_brief_history_v1/summary.json")
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
                "recommendation": str(payload.get("recommendation") or "unknown"),
                "anchor_brief_score": round(_to_float(payload.get("anchor_brief_score", 0.0)), 4),
                "confidence_band": str(payload.get("confidence_band") or "unknown"),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}

    publish_count = len([r for r in rows if str(r.get("recommendation") or "") == "PUBLISH"])
    guarded_count = len([r for r in rows if str(r.get("recommendation") or "") == "PUBLISH_WITH_GUARDS"])
    hold_count = len([r for r in rows if str(r.get("recommendation") or "") == "HOLD"])

    avg_score = round(sum(_to_float(r.get("anchor_brief_score", 0.0)) for r in rows) / max(1, total), 4)
    publish_rate = round(publish_count / max(1, total), 4)

    alerts: list[str] = []
    if str(latest.get("recommendation") or "") in {"HOLD", "PUBLISH_WITH_GUARDS"}:
        alerts.append("latest_recommendation_not_publish")
    if hold_count > 0 and total >= 3:
        alerts.append("hold_recommendation_present")

    status = "PASS" if not alerts else "NEEDS_REVIEW"

    out = {
        "generated_at_utc": now,
        "status": status,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "latest_status": latest.get("status"),
        "latest_recommendation": latest.get("recommendation"),
        "latest_anchor_brief_score": latest.get("anchor_brief_score"),
        "avg_anchor_brief_score": avg_score,
        "publish_rate": publish_rate,
        "publish_with_guards_count": guarded_count,
        "hold_count": hold_count,
        "alerts": alerts,
    }

    _write_json(args.out, out)
    _write_markdown(args.report_out or _default_md_path(args.out), out)
    print(json.dumps({"status": status, "total_records": total, "avg_anchor_brief_score": avg_score}))


if __name__ == "__main__":
    main()
