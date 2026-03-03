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
        "# GateForge Mutation Source Provenance History Ledger v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_existing_source_path_ratio_pct: `{payload.get('latest_existing_source_path_ratio_pct')}`",
        f"- latest_allowed_root_ratio_pct: `{payload.get('latest_allowed_root_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append mutation source-provenance history and emit summary")
    parser.add_argument("--mutation-source-provenance-summary", required=True)
    parser.add_argument("--ledger", default="artifacts/private_model_mutation_scale_batch_v1/state/mutation_source_provenance_history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_mutation_source_provenance_history_ledger_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    guard = _load_json(args.mutation_source_provenance_summary)
    reasons: list[str] = []
    if not guard:
        reasons.append("mutation_source_provenance_summary_missing")

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    row = {
        "recorded_at_utc": now,
        "guard_status": str(guard.get("status") or "UNKNOWN"),
        "total_mutations": _to_int(guard.get("total_mutations", 0)),
        "existing_source_path_ratio_pct": _to_float(guard.get("existing_source_path_ratio_pct", 0.0)),
        "allowed_root_ratio_pct": _to_float(guard.get("allowed_root_ratio_pct", 0.0)),
        "registry_match_ratio_pct": _to_float(guard.get("registry_match_ratio_pct", 0.0)),
    }
    if not reasons:
        _append_jsonl(ledger_path, [row])

    rows = _load_jsonl(ledger_path)
    total_records = len(rows)
    latest = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) >= 2 else {}
    delta_existing_ratio = round(
        _to_float(latest.get("existing_source_path_ratio_pct", 0.0))
        - _to_float(previous.get("existing_source_path_ratio_pct", 0.0)),
        4,
    )
    delta_allowed_ratio = round(
        _to_float(latest.get("allowed_root_ratio_pct", 0.0))
        - _to_float(previous.get("allowed_root_ratio_pct", 0.0)),
        4,
    )

    alerts: list[str] = []
    if str(latest.get("guard_status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_mutation_source_provenance_not_pass")
    if _to_float(latest.get("existing_source_path_ratio_pct", 0.0)) < 95.0:
        alerts.append("latest_existing_source_path_ratio_below_95pct")
    if _to_float(latest.get("allowed_root_ratio_pct", 0.0)) < 95.0:
        alerts.append("latest_allowed_root_ratio_below_95pct")
    if total_records >= 2 and delta_existing_ratio < 0:
        alerts.append("existing_source_path_ratio_decreasing")
    if total_records >= 2 and delta_allowed_ratio < 0:
        alerts.append("allowed_root_ratio_decreasing")

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
        "latest_existing_source_path_ratio_pct": latest.get("existing_source_path_ratio_pct"),
        "latest_allowed_root_ratio_pct": latest.get("allowed_root_ratio_pct"),
        "latest_registry_match_ratio_pct": latest.get("registry_match_ratio_pct"),
        "delta_existing_source_path_ratio_pct": delta_existing_ratio,
        "delta_allowed_root_ratio_pct": delta_allowed_ratio,
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
                "latest_existing_source_path_ratio_pct": payload.get("latest_existing_source_path_ratio_pct"),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
