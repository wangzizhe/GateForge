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


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Freeze History Ledger v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_freeze_status: `{payload.get('latest_freeze_status')}`",
        f"- avg_accepted_models: `{payload.get('avg_accepted_models')}`",
        f"- avg_generated_mutations: `{payload.get('avg_generated_mutations')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append weekly freeze summaries to ledger and compute freeze history KPIs")
    parser.add_argument("--record", action="append", default=[])
    parser.add_argument("--ledger", default="artifacts/dataset_real_model_mutation_freeze_history_ledger_v1/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_real_model_mutation_freeze_history_ledger_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)

    reasons: list[str] = []
    rows_to_append: list[dict] = []
    for record_path in args.record:
        payload = _load_json(record_path)
        if not payload:
            reasons.append(f"record_missing:{record_path}")
            continue
        rows_to_append.append(
            {
                "recorded_at_utc": now,
                "source_record_path": record_path,
                "freeze_id": str(payload.get("freeze_id") or ""),
                "week_tag": str(payload.get("week_tag") or ""),
                "status": str(payload.get("status") or "UNKNOWN"),
                "accepted_models": _to_int(payload.get("accepted_models", 0)),
                "generated_mutations": _to_int(payload.get("generated_mutations", 0)),
                "reproducible_mutations": _to_int(payload.get("reproducible_mutations", 0)),
                "canonical_net_growth_models": _to_int(payload.get("canonical_net_growth_models", 0)),
                "validation_type_match_rate_pct": round(_to_float(payload.get("validation_type_match_rate_pct", 0.0)), 4),
                "distribution_guard_status": str(payload.get("distribution_guard_status") or "UNKNOWN"),
            }
        )
    if rows_to_append:
        _append_jsonl(ledger_path, rows_to_append)

    rows = _load_jsonl(ledger_path)
    total_records = len(rows)
    latest = rows[-1] if rows else {}

    status_counts = {"PASS": 0, "NEEDS_REVIEW": 0, "FAIL": 0, "UNKNOWN": 0}
    total_accepted = 0
    total_generated = 0
    total_reproducible = 0
    total_growth = 0
    total_type_match = 0.0
    for row in rows:
        status = str(row.get("status") or "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
        total_accepted += _to_int(row.get("accepted_models", 0))
        total_generated += _to_int(row.get("generated_mutations", 0))
        total_reproducible += _to_int(row.get("reproducible_mutations", 0))
        total_growth += _to_int(row.get("canonical_net_growth_models", 0))
        total_type_match += _to_float(row.get("validation_type_match_rate_pct", 0.0))

    avg_accepted_models = round(total_accepted / max(1, total_records), 4)
    avg_generated_mutations = round(total_generated / max(1, total_records), 4)
    avg_reproducible_mutations = round(total_reproducible / max(1, total_records), 4)
    avg_canonical_net_growth_models = round(total_growth / max(1, total_records), 4)
    avg_validation_type_match_rate_pct = round(total_type_match / max(1, total_records), 4)

    needs_review_rate = round(
        (status_counts.get("NEEDS_REVIEW", 0) + status_counts.get("FAIL", 0)) / max(1, total_records),
        4,
    )

    alerts: list[str] = []
    if str(latest.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_freeze_status_not_pass")
    if total_records >= 3 and avg_canonical_net_growth_models <= 0:
        alerts.append("avg_canonical_net_growth_not_positive")
    if total_records >= 3 and avg_validation_type_match_rate_pct < 60.0:
        alerts.append("avg_validation_type_match_low")
    if total_records >= 3 and needs_review_rate >= 0.34:
        alerts.append("freeze_needs_review_rate_high")

    status = "PASS"
    if reasons and not rows:
        status = "FAIL"
    elif alerts or reasons:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": now,
        "status": status,
        "ledger_path": str(ledger_path),
        "ingested_count": len(rows_to_append),
        "total_records": total_records,
        "status_counts": status_counts,
        "latest_freeze_status": latest.get("status"),
        "latest_week_tag": latest.get("week_tag"),
        "latest_freeze_id": latest.get("freeze_id"),
        "avg_accepted_models": avg_accepted_models,
        "avg_generated_mutations": avg_generated_mutations,
        "avg_reproducible_mutations": avg_reproducible_mutations,
        "avg_canonical_net_growth_models": avg_canonical_net_growth_models,
        "avg_validation_type_match_rate_pct": avg_validation_type_match_rate_pct,
        "needs_review_rate": needs_review_rate,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_records": total_records, "needs_review_rate": needs_review_rate}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
