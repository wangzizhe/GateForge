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
        "# GateForge Mutation Selection History Ledger v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_selected_models: `{payload.get('latest_selected_models')}`",
        f"- latest_selected_large_ratio_pct: `{payload.get('latest_selected_large_ratio_pct')}`",
        f"- latest_max_family_share_pct: `{payload.get('latest_max_family_share_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append mutation selection quality history and emit rollup summary")
    parser.add_argument("--selection-plan-summary", required=True)
    parser.add_argument("--selection-balance-guard-summary", required=True)
    parser.add_argument("--mutation-pack-summary", required=True)
    parser.add_argument("--ledger", default="artifacts/private_model_mutation_scale_batch_v1/state/mutation_selection_history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_mutation_selection_history_ledger_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    plan = _load_json(args.selection_plan_summary)
    guard = _load_json(args.selection_balance_guard_summary)
    pack = _load_json(args.mutation_pack_summary)

    reasons: list[str] = []
    if not plan:
        reasons.append("selection_plan_summary_missing")
    if not guard:
        reasons.append("selection_balance_guard_summary_missing")
    if not pack:
        reasons.append("mutation_pack_summary_missing")

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    row = {
        "recorded_at_utc": now,
        "selection_plan_status": str(plan.get("status") or "UNKNOWN"),
        "selection_guard_status": str(guard.get("status") or "UNKNOWN"),
        "selected_models": _to_int(plan.get("selected_models", 0)),
        "selected_large_ratio_pct": round(_to_float(plan.get("selected_large_ratio_pct", 0.0)), 4),
        "selected_families": _to_int(plan.get("selected_families", 0)),
        "selected_source_buckets": _to_int(plan.get("selected_source_buckets", 0)),
        "max_family_share_pct": round(_to_float(plan.get("max_family_share_pct", 0.0)), 4),
        "generated_mutations": _to_int(pack.get("total_mutations", 0)),
        "mutations_per_selected_model": round(
            _to_int(pack.get("total_mutations", 0)) / max(1, _to_int(plan.get("selected_models", 0))),
            4,
        ),
    }
    if not reasons:
        _append_jsonl(ledger_path, [row])

    rows = _load_jsonl(ledger_path)
    total_records = len(rows)
    latest = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) >= 2 else {}
    avg_large_ratio = round(
        sum(_to_float(r.get("selected_large_ratio_pct", 0.0)) for r in rows) / max(1, total_records),
        4,
    )
    avg_family_share = round(
        sum(_to_float(r.get("max_family_share_pct", 0.0)) for r in rows) / max(1, total_records),
        4,
    )

    delta_large_ratio = round(
        _to_float(latest.get("selected_large_ratio_pct", 0.0)) - _to_float(previous.get("selected_large_ratio_pct", 0.0)),
        4,
    )
    delta_family_coverage = _to_int(latest.get("selected_families", 0)) - _to_int(previous.get("selected_families", 0))
    delta_source_coverage = _to_int(latest.get("selected_source_buckets", 0)) - _to_int(previous.get("selected_source_buckets", 0))
    delta_family_share = round(
        _to_float(latest.get("max_family_share_pct", 0.0)) - _to_float(previous.get("max_family_share_pct", 0.0)),
        4,
    )

    alerts: list[str] = []
    if str(latest.get("selection_guard_status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_selection_guard_not_pass")
    if _to_float(latest.get("selected_large_ratio_pct", 0.0)) < 25.0:
        alerts.append("latest_selected_large_ratio_below_25pct")
    if _to_float(latest.get("max_family_share_pct", 0.0)) > 65.0:
        alerts.append("latest_family_concentration_above_65pct")
    if total_records >= 2 and delta_large_ratio < 0:
        alerts.append("selected_large_ratio_decreasing")
    if total_records >= 2 and delta_family_coverage < 0:
        alerts.append("selected_family_coverage_decreasing")
    if total_records >= 2 and delta_source_coverage < 0:
        alerts.append("selected_source_coverage_decreasing")
    if total_records >= 2 and delta_family_share > 0:
        alerts.append("family_concentration_increasing")

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
        "latest_selected_models": latest.get("selected_models"),
        "latest_selected_large_ratio_pct": latest.get("selected_large_ratio_pct"),
        "latest_selected_families": latest.get("selected_families"),
        "latest_selected_source_buckets": latest.get("selected_source_buckets"),
        "latest_max_family_share_pct": latest.get("max_family_share_pct"),
        "avg_selected_large_ratio_pct": avg_large_ratio,
        "avg_max_family_share_pct": avg_family_share,
        "delta_selected_large_ratio_pct": delta_large_ratio,
        "delta_selected_family_coverage": delta_family_coverage,
        "delta_selected_source_coverage": delta_source_coverage,
        "delta_max_family_share_pct": delta_family_share,
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
                "latest_selected_models": payload.get("latest_selected_models"),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
