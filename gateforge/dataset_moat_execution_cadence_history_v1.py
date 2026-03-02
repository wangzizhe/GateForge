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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Moat Execution Cadence History v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_execution_cadence_score: `{payload.get('latest_execution_cadence_score')}`",
        f"- avg_execution_cadence_score: `{payload.get('avg_execution_cadence_score')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append moat execution cadence summary and emit history")
    parser.add_argument("--moat-execution-cadence-summary", required=True)
    parser.add_argument("--ledger", default="artifacts/dataset_moat_execution_cadence_history_v1/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_moat_execution_cadence_history_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    cadence = _load_json(args.moat_execution_cadence_summary)

    reasons: list[str] = []
    if not cadence:
        reasons.append("moat_execution_cadence_summary_missing")

    ledger = Path(args.ledger)
    if cadence:
        row = {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": str(cadence.get("status") or "UNKNOWN"),
            "execution_cadence_score": round(_to_float(cadence.get("execution_cadence_score", 0.0)), 4),
            "weekly_model_target": int(cadence.get("weekly_model_target", 0) or 0),
            "weekly_mutation_target": int(cadence.get("weekly_mutation_target", 0) or 0),
        }
        _append_jsonl(ledger, row)

    rows = _read_jsonl(ledger)
    total = len(rows)
    latest = rows[-1] if rows else {}

    avg_score = round(sum(_to_float(r.get("execution_cadence_score", 0.0)) for r in rows) / max(1, total), 4)
    avg_model_target = round(sum(_to_float(r.get("weekly_model_target", 0.0)) for r in rows) / max(1, total), 4)

    alerts: list[str] = []
    if str(latest.get("status") or "") != "PASS":
        alerts.append("latest_execution_cadence_not_pass")
    if avg_score < 72.0 and total >= 3:
        alerts.append("avg_execution_cadence_score_low")

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
        "latest_execution_cadence_score": latest.get("execution_cadence_score"),
        "avg_execution_cadence_score": avg_score,
        "avg_weekly_model_target": avg_model_target,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "moat_execution_cadence_summary": args.moat_execution_cadence_summary,
            "ledger": str(ledger),
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_records": total, "avg_execution_cadence_score": avg_score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
