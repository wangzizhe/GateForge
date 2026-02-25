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
        "# GateForge Dataset Policy Auto-Tune History",
        "",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_suggested_profile: `{payload.get('latest_suggested_profile')}`",
        f"- latest_suggested_action: `{payload.get('latest_suggested_action')}`",
        f"- latest_confidence: `{payload.get('latest_confidence')}`",
        f"- strict_suggestion_rate: `{payload.get('strict_suggestion_rate')}`",
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
    parser = argparse.ArgumentParser(description="Append dataset strategy advisor results to history and summarize")
    parser.add_argument("--record", action="append", default=[], help="Advisor JSON path (repeatable)")
    parser.add_argument("--ledger", default="artifacts/dataset_policy_autotune_history/history.jsonl", help="History JSONL path")
    parser.add_argument("--out", default="artifacts/dataset_policy_autotune_history/summary.json", help="History summary JSON path")
    parser.add_argument("--report-out", default=None, help="History summary markdown path")
    parser.add_argument("--strict-confidence-threshold", type=float, default=0.8)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    append_rows: list[dict] = []
    for path in args.record:
        payload = _load_json(path)
        advice = payload.get("advice") if isinstance(payload.get("advice"), dict) else {}
        profile = str(advice.get("suggested_policy_profile") or "")
        confidence = float(advice.get("confidence", 0.0) or 0.0)
        append_rows.append(
            {
                "recorded_at_utc": now,
                "source_record_path": path,
                "suggested_profile": profile,
                "suggested_action": advice.get("suggested_action"),
                "confidence": confidence,
                "reasons_count": len(advice.get("reasons") or []),
                "strict_suggestion": profile == "dataset_strict" or confidence >= args.strict_confidence_threshold,
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}
    strict_count = sum(1 for r in rows if bool(r.get("strict_suggestion")))
    strict_rate = round(strict_count / max(1, total), 4)
    avg_confidence = round(sum(_to_float(r.get("confidence", 0.0)) for r in rows) / max(1, total), 4)

    alerts: list[str] = []
    if bool(latest.get("strict_suggestion")):
        alerts.append("latest_suggests_tighten")
    if strict_rate >= 0.5 and total >= 3:
        alerts.append("strict_suggestion_rate_high")
    if _to_float(latest.get("confidence", 0.0)) < 0.6:
        alerts.append("latest_confidence_low")

    summary = {
        "generated_at_utc": now,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "latest_suggested_profile": latest.get("suggested_profile"),
        "latest_suggested_action": latest.get("suggested_action"),
        "latest_confidence": _to_float(latest.get("confidence", 0.0)),
        "latest_reasons_count": int(latest.get("reasons_count", 0) or 0),
        "strict_suggestion_rate": strict_rate,
        "avg_confidence": avg_confidence,
        "alerts": alerts,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"total_records": total, "strict_suggestion_rate": strict_rate, "alerts": alerts}))


if __name__ == "__main__":
    main()

