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
        "# GateForge Mutation Depth Pressure History v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_pressure_index: `{payload.get('latest_pressure_index')}`",
        f"- avg_pressure_index: `{payload.get('avg_pressure_index')}`",
        f"- avg_high_risk_gap_count: `{payload.get('avg_high_risk_gap_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append mutation depth pressure board summaries and emit history statistics")
    parser.add_argument("--mutation-depth-pressure-board-summary", required=True)
    parser.add_argument("--ledger", default="artifacts/dataset_mutation_depth_pressure_history_v1/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_mutation_depth_pressure_history_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    board = _load_json(args.mutation_depth_pressure_board_summary)

    reasons: list[str] = []
    if not board:
        reasons.append("mutation_depth_pressure_board_summary_missing")

    ledger = Path(args.ledger)
    if board:
        row = {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": str(board.get("status") or "UNKNOWN"),
            "mutation_depth_pressure_index": round(_to_float(board.get("mutation_depth_pressure_index", 0.0)), 4),
            "high_risk_gap_count": _to_int(board.get("high_risk_gap_count", 0)),
            "missing_recipe_count": _to_int(board.get("missing_recipe_count", 0)),
            "recommended_weekly_mutation_target": _to_int(board.get("recommended_weekly_mutation_target", 0)),
        }
        _append_jsonl(ledger, row)

    rows = _read_jsonl(ledger)
    total = len(rows)
    latest = rows[-1] if rows else {}

    avg_pressure = round(sum(_to_float(r.get("mutation_depth_pressure_index", 0.0)) for r in rows) / max(1, total), 4)
    avg_high_risk = round(sum(_to_float(r.get("high_risk_gap_count", 0.0)) for r in rows) / max(1, total), 4)
    avg_missing_recipe = round(sum(_to_float(r.get("missing_recipe_count", 0.0)) for r in rows) / max(1, total), 4)

    alerts: list[str] = []
    if str(latest.get("status") or "") != "PASS":
        alerts.append("latest_depth_pressure_not_pass")
    if avg_pressure > 35.0 and total >= 3:
        alerts.append("avg_pressure_index_high")
    if avg_high_risk >= 1.0 and total >= 3:
        alerts.append("avg_high_risk_gap_count_non_zero")

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
        "latest_pressure_index": latest.get("mutation_depth_pressure_index"),
        "latest_high_risk_gap_count": latest.get("high_risk_gap_count"),
        "latest_missing_recipe_count": latest.get("missing_recipe_count"),
        "avg_pressure_index": avg_pressure,
        "avg_high_risk_gap_count": avg_high_risk,
        "avg_missing_recipe_count": avg_missing_recipe,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_depth_pressure_board_summary": args.mutation_depth_pressure_board_summary,
            "ledger": str(ledger),
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_records": total, "avg_pressure_index": avg_pressure}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
