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
        "# GateForge Failure Distribution Stability History v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_status: `{payload.get('latest_status')}`",
        f"- avg_stability_score: `{payload.get('avg_stability_score')}`",
        f"- avg_rare_failure_replay_rate: `{payload.get('avg_rare_failure_replay_rate')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append failure distribution stability summaries and emit history")
    parser.add_argument("--record", action="append", default=[])
    parser.add_argument("--ledger", default="artifacts/dataset_failure_distribution_stability_history_v1/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_failure_distribution_stability_history_v1/summary.json")
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
                "stability_score": round(_to_float(payload.get("stability_score", 0.0)), 4),
                "distribution_drift_score": round(_to_float(payload.get("distribution_drift_score", 0.0)), 4),
                "regression_rate_after": round(_to_float(payload.get("regression_rate_after", 0.0)), 4),
                "rare_failure_replay_rate": round(_to_float(payload.get("rare_failure_replay_rate", 0.0)), 4),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}

    avg_score = round(sum(_to_float(r.get("stability_score", 0.0)) for r in rows) / max(1, total), 4)
    avg_drift = round(sum(_to_float(r.get("distribution_drift_score", 0.0)) for r in rows) / max(1, total), 4)
    avg_replay = round(sum(_to_float(r.get("rare_failure_replay_rate", 0.0)) for r in rows) / max(1, total), 4)

    alerts: list[str] = []
    if str(latest.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_stability_not_pass")
    if avg_score < 75.0 and total >= 3:
        alerts.append("avg_stability_score_low")
    if avg_replay < 0.6 and total >= 3:
        alerts.append("avg_rare_failure_replay_rate_low")

    status = "PASS" if not alerts else "NEEDS_REVIEW"

    out = {
        "generated_at_utc": now,
        "status": status,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "latest_status": latest.get("status"),
        "latest_stability_score": latest.get("stability_score"),
        "latest_distribution_drift_score": latest.get("distribution_drift_score"),
        "latest_rare_failure_replay_rate": latest.get("rare_failure_replay_rate"),
        "avg_stability_score": avg_score,
        "avg_distribution_drift_score": avg_drift,
        "avg_rare_failure_replay_rate": avg_replay,
        "alerts": alerts,
    }

    _write_json(args.out, out)
    _write_markdown(args.report_out or _default_md_path(args.out), out)
    print(json.dumps({"status": status, "total_records": total, "avg_stability_score": avg_score}))


if __name__ == "__main__":
    main()
