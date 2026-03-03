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
        "# GateForge Mutation Execution Authenticity History Ledger v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_solver_command_ratio_pct: `{payload.get('latest_solver_command_ratio_pct')}`",
        f"- latest_probe_only_command_ratio_pct: `{payload.get('latest_probe_only_command_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append mutation execution authenticity history and emit summary")
    parser.add_argument("--mutation-execution-authenticity-summary", required=True)
    parser.add_argument("--ledger", default="artifacts/private_model_mutation_scale_batch_v1/state/mutation_execution_authenticity_history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_mutation_execution_authenticity_history_ledger_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    guard = _load_json(args.mutation_execution_authenticity_summary)
    reasons: list[str] = []
    if not guard:
        reasons.append("mutation_execution_authenticity_summary_missing")

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    row = {
        "recorded_at_utc": now,
        "guard_status": str(guard.get("status") or "UNKNOWN"),
        "total_mutations": _to_int(guard.get("total_mutations", 0)),
        "solver_command_ratio_pct": _to_float(guard.get("solver_command_ratio_pct", 0.0)),
        "probe_only_command_ratio_pct": _to_float(guard.get("probe_only_command_ratio_pct", 0.0)),
        "placeholder_executed_ratio_pct": _to_float(guard.get("placeholder_executed_ratio_pct", 0.0)),
        "observed_coverage_ratio_pct": _to_float(guard.get("observed_coverage_ratio_pct", 0.0)),
    }
    if not reasons:
        _append_jsonl(ledger_path, [row])

    rows = _load_jsonl(ledger_path)
    total_records = len(rows)
    latest = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) >= 2 else {}

    delta_solver_ratio = round(
        _to_float(latest.get("solver_command_ratio_pct", 0.0))
        - _to_float(previous.get("solver_command_ratio_pct", 0.0)),
        4,
    )
    delta_probe_ratio = round(
        _to_float(latest.get("probe_only_command_ratio_pct", 0.0))
        - _to_float(previous.get("probe_only_command_ratio_pct", 0.0)),
        4,
    )

    alerts: list[str] = []
    if str(latest.get("guard_status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_mutation_execution_authenticity_not_pass")
    if _to_float(latest.get("solver_command_ratio_pct", 0.0)) < 1.0:
        alerts.append("latest_solver_command_ratio_below_1pct")
    if _to_float(latest.get("probe_only_command_ratio_pct", 0.0)) > 90.0:
        alerts.append("latest_probe_only_command_ratio_above_90pct")
    if total_records >= 2 and delta_solver_ratio < 0:
        alerts.append("solver_command_ratio_decreasing")
    if total_records >= 2 and delta_probe_ratio > 0:
        alerts.append("probe_only_command_ratio_increasing")

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
        "latest_solver_command_ratio_pct": latest.get("solver_command_ratio_pct"),
        "latest_probe_only_command_ratio_pct": latest.get("probe_only_command_ratio_pct"),
        "latest_placeholder_executed_ratio_pct": latest.get("placeholder_executed_ratio_pct"),
        "latest_observed_coverage_ratio_pct": latest.get("observed_coverage_ratio_pct"),
        "delta_solver_command_ratio_pct": delta_solver_ratio,
        "delta_probe_only_command_ratio_pct": delta_probe_ratio,
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
                "latest_solver_command_ratio_pct": payload.get("latest_solver_command_ratio_pct"),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
