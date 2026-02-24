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
        "# GateForge Policy Auto-Tune Governance History",
        "",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_effectiveness_decision: `{payload.get('latest_effectiveness_decision')}`",
        f"- improvement_rate: `{payload.get('improvement_rate')}`",
        f"- regression_rate: `{payload.get('regression_rate')}`",
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
    parser = argparse.ArgumentParser(description="Append policy autotune governance summaries to history and summarize")
    parser.add_argument("--record", action="append", default=[], help="Governance demo summary JSON path (repeatable)")
    parser.add_argument(
        "--ledger",
        default="artifacts/policy_autotune_governance_history/history.jsonl",
        help="History JSONL path",
    )
    parser.add_argument(
        "--out",
        default="artifacts/policy_autotune_governance_history/summary.json",
        help="History summary JSON path",
    )
    parser.add_argument("--report-out", default=None, help="History summary markdown path")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)

    append_rows: list[dict] = []
    for path in args.record:
        payload = _load_json(path)
        decision = str(payload.get("effectiveness_decision") or "UNKNOWN")
        append_rows.append(
            {
                "recorded_at_utc": now,
                "source_record_path": path,
                "advisor_profile": payload.get("advisor_profile"),
                "baseline_compare_status": payload.get("baseline_compare_status"),
                "tuned_compare_status": payload.get("tuned_compare_status"),
                "baseline_apply_status": payload.get("baseline_apply_status"),
                "tuned_apply_status": payload.get("tuned_apply_status"),
                "effectiveness_decision": decision,
                "delta_apply_score": payload.get("delta_apply_score"),
                "delta_compare_score": payload.get("delta_compare_score"),
                "is_improved": decision == "IMPROVED",
                "is_regressed": decision == "REGRESSED",
            }
        )

    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}

    improved_count = sum(1 for r in rows if bool(r.get("is_improved")))
    regressed_count = sum(1 for r in rows if bool(r.get("is_regressed")))
    unchanged_count = total - improved_count - regressed_count

    improvement_rate = round(improved_count / max(1, total), 4)
    regression_rate = round(regressed_count / max(1, total), 4)

    alerts: list[str] = []
    if bool(latest.get("is_regressed")):
        alerts.append("latest_run_regressed")
    if regression_rate >= 0.3 and total >= 3:
        alerts.append("regression_rate_high")
    if improvement_rate <= 0.2 and total >= 3:
        alerts.append("improvement_rate_low")

    summary = {
        "generated_at_utc": now,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "latest_effectiveness_decision": latest.get("effectiveness_decision"),
        "latest_advisor_profile": latest.get("advisor_profile"),
        "improved_count": improved_count,
        "regressed_count": regressed_count,
        "unchanged_count": unchanged_count,
        "improvement_rate": improvement_rate,
        "regression_rate": regression_rate,
        "alerts": alerts,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"total_records": total, "improvement_rate": improvement_rate, "alerts": alerts}))


if __name__ == "__main__":
    main()
