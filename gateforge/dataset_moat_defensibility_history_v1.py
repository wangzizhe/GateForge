from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if not t:
            continue
        try:
            obj = json.loads(t)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


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
        "# GateForge Moat Defensibility History v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_defensibility_score: `{payload.get('latest_defensibility_score')}`",
        f"- avg_defensibility_score: `{payload.get('avg_defensibility_score')}`",
        f"- pass_rate_pct: `{payload.get('pass_rate_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append moat defensibility report into history")
    parser.add_argument("--moat-defensibility-report-summary", required=True)
    parser.add_argument("--ledger", default="artifacts/dataset_moat_defensibility_history_v1/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_moat_defensibility_history_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    report = _load_json(args.moat_defensibility_report_summary)

    reasons: list[str] = []
    if not report:
        reasons.append("moat_defensibility_report_summary_missing")

    ledger = Path(args.ledger)
    if report:
        row = {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": str(report.get("status") or "UNKNOWN"),
            "moat_defensibility_score": round(_to_float(report.get("moat_defensibility_score", 0.0)), 4),
            "defensibility_band": str(report.get("defensibility_band") or "UNKNOWN"),
            "key_alert_count": _to_int(report.get("key_alert_count", 0)),
        }
        _append_jsonl(ledger, row)

    rows = _read_jsonl(ledger)
    total = len(rows)
    latest = rows[-1] if rows else {}

    avg_score = round(sum(_to_float(r.get("moat_defensibility_score", 0.0)) for r in rows) / max(1, total), 4)
    avg_alert = round(sum(_to_float(r.get("key_alert_count", 0.0)) for r in rows) / max(1, total), 4)

    pass_count = sum(1 for r in rows if str(r.get("status") or "") == "PASS")
    pass_rate = round((pass_count / max(1, total)) * 100.0, 2)

    publish_ready_streak = 0
    for r in reversed(rows):
        if str(r.get("status") or "") == "PASS" and _to_float(r.get("moat_defensibility_score", 0.0)) >= 75.0:
            publish_ready_streak += 1
        else:
            break

    alerts: list[str] = []
    if str(latest.get("status") or "") != "PASS":
        alerts.append("latest_defensibility_not_pass")
    if avg_score < 72.0 and total >= 3:
        alerts.append("avg_defensibility_score_low")
    if avg_alert > 1.0 and total >= 3:
        alerts.append("avg_key_alert_count_high")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_records": total,
        "latest_status": latest.get("status"),
        "latest_defensibility_score": latest.get("moat_defensibility_score"),
        "latest_key_alert_count": latest.get("key_alert_count"),
        "avg_defensibility_score": avg_score,
        "avg_key_alert_count": avg_alert,
        "pass_rate_pct": pass_rate,
        "publish_ready_streak": publish_ready_streak,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "moat_defensibility_report_summary": args.moat_defensibility_report_summary,
            "ledger": str(ledger),
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_records": total, "avg_defensibility_score": avg_score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
