from __future__ import annotations

import argparse
import json
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


def _to_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _extract_deduplicated_cases(payload: dict) -> int:
    return _to_int(
        payload.get(
            "build_deduplicated_cases",
            payload.get("deduplicated_cases", payload.get("total_cases", 0)),
        )
    )


def _extract_failure_case_rate(payload: dict) -> float:
    return _to_float(
        payload.get("quality_failure_case_rate", payload.get("failure_case_rate", 0.0))
    )


def _extract_freeze_status(payload: dict) -> str:
    return str(payload.get("freeze_status") or "UNKNOWN")


def _extract_bundle_status(payload: dict) -> str:
    return str(payload.get("bundle_status") or payload.get("status") or "UNKNOWN")


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Dataset History",
        "",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_deduplicated_cases: `{payload.get('latest_deduplicated_cases')}`",
        f"- avg_deduplicated_cases: `{payload.get('avg_deduplicated_cases')}`",
        f"- latest_failure_case_rate: `{payload.get('latest_failure_case_rate')}`",
        f"- avg_failure_case_rate: `{payload.get('avg_failure_case_rate')}`",
        f"- latest_freeze_status: `{payload.get('latest_freeze_status')}`",
        f"- freeze_pass_rate: `{payload.get('freeze_pass_rate')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = payload.get("alerts", [])
    if isinstance(alerts, list) and alerts:
        for item in alerts:
            lines.append(f"- `{item}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append dataset pipeline summaries to history ledger")
    parser.add_argument("--record", action="append", default=[], help="Path to dataset summary JSON (repeatable)")
    parser.add_argument(
        "--ledger",
        default="artifacts/dataset/history.jsonl",
        help="Dataset history ledger JSONL path",
    )
    parser.add_argument(
        "--out",
        default="artifacts/dataset/history_summary.json",
        help="Dataset history summary JSON path",
    )
    parser.add_argument("--report-out", default=None, help="Dataset history summary markdown path")
    parser.add_argument("--min-deduplicated-cases", type=int, default=10, help="Alert threshold for latest deduplicated case count")
    parser.add_argument("--min-failure-case-rate", type=float, default=0.2, help="Alert threshold for latest failure case rate")
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
                "deduplicated_cases": _extract_deduplicated_cases(payload),
                "failure_case_rate": _extract_failure_case_rate(payload),
                "freeze_status": _extract_freeze_status(payload),
                "bundle_status": _extract_bundle_status(payload),
            }
        )

    if append_rows:
        _append_rows(ledger_path, append_rows)

    rows = _load_ledger(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}
    avg_dedup = round(sum(_to_int(r.get("deduplicated_cases")) for r in rows) / total, 4) if total else 0.0
    avg_failure_rate = round(sum(_to_float(r.get("failure_case_rate")) for r in rows) / total, 4) if total else 0.0
    freeze_pass_count = sum(1 for r in rows if str(r.get("freeze_status") or "") == "PASS")
    freeze_pass_rate = round(freeze_pass_count / total, 4) if total else 0.0
    bundle_fail_count = sum(1 for r in rows if str(r.get("bundle_status") or "") == "FAIL")

    latest_dedup = _to_int(latest.get("deduplicated_cases"))
    latest_failure_rate = _to_float(latest.get("failure_case_rate"))
    latest_freeze = str(latest.get("freeze_status") or "UNKNOWN")

    alerts: list[str] = []
    if 0 < latest_dedup < max(1, int(args.min_deduplicated_cases)):
        alerts.append("latest_deduplicated_case_count_low")
    if latest_failure_rate < float(args.min_failure_case_rate):
        alerts.append("latest_failure_case_rate_low")
    if latest_freeze != "PASS":
        alerts.append("latest_freeze_not_pass")
    if bundle_fail_count > 0:
        alerts.append("historical_dataset_bundle_fail")

    summary = {
        "generated_at_utc": now,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "latest_deduplicated_cases": latest_dedup,
        "avg_deduplicated_cases": avg_dedup,
        "latest_failure_case_rate": latest_failure_rate,
        "avg_failure_case_rate": avg_failure_rate,
        "latest_freeze_status": latest_freeze,
        "freeze_pass_rate": freeze_pass_rate,
        "alerts": alerts,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"total_records": total, "latest_freeze_status": latest_freeze, "alerts": alerts}))


if __name__ == "__main__":
    main()
