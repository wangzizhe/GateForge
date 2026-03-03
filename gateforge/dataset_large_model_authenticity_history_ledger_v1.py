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


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        rows.append(json.loads(text))
    return rows


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True))
            f.write("\n")


def _write_json(path: str, payload: object) -> None:
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
        "# GateForge Large Model Authenticity History Ledger v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_large_model_authenticity_score: `{payload.get('latest_large_model_authenticity_score')}`",
        f"- delta_large_model_authenticity_score: `{payload.get('delta_large_model_authenticity_score')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append large-model authenticity history and emit summary")
    parser.add_argument("--large-model-authenticity-summary", required=True)
    parser.add_argument("--ledger", default="artifacts/private_model_mutation_scale_batch_v1/state/large_model_authenticity_history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_large_model_authenticity_history_ledger_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    summary = _load_json(args.large_model_authenticity_summary)
    reasons: list[str] = []
    if not summary:
        reasons.append("large_model_authenticity_summary_missing")

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    row = {
        "recorded_at_utc": now,
        "gate_status": str(summary.get("status") or "UNKNOWN"),
        "large_model_authenticity_score": _to_float(summary.get("large_model_authenticity_score", 0.0)),
        "failed_gate_count": _to_int(summary.get("failed_gate_count", 0)),
        "critical_failed_gate_count": _to_int(summary.get("critical_failed_gate_count", 0)),
    }
    if not reasons:
        _append_jsonl(ledger_path, [row])

    rows = _load_jsonl(ledger_path)
    total_records = len(rows)
    latest = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) >= 2 else {}
    delta_score = round(
        _to_float(latest.get("large_model_authenticity_score", 0.0))
        - _to_float(previous.get("large_model_authenticity_score", 0.0)),
        4,
    )

    alerts: list[str] = []
    if str(latest.get("gate_status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_large_model_authenticity_not_pass")
    if _to_float(latest.get("large_model_authenticity_score", 0.0)) < 65.0:
        alerts.append("latest_large_model_authenticity_score_below_65")
    if total_records >= 2 and delta_score < 0:
        alerts.append("large_model_authenticity_score_decreasing")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": now,
        "status": status,
        "ledger_path": str(ledger_path),
        "total_records": total_records,
        "latest_large_model_authenticity_score": latest.get("large_model_authenticity_score"),
        "latest_failed_gate_count": latest.get("failed_gate_count"),
        "latest_critical_failed_gate_count": latest.get("critical_failed_gate_count"),
        "delta_large_model_authenticity_score": delta_score,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "total_records": total_records,
                "latest_large_model_authenticity_score": payload.get("latest_large_model_authenticity_score"),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
