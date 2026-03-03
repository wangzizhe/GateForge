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


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Repro Depth History Ledger v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_tracked_models: `{payload.get('latest_tracked_models')}`",
        f"- latest_models_meeting_depth_ratio_pct: `{payload.get('latest_models_meeting_depth_ratio_pct')}`",
        f"- latest_max_model_share_pct: `{payload.get('latest_max_model_share_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append mutation reproducibility depth history and emit summary")
    parser.add_argument("--mutation-repro-depth-guard-summary", required=True)
    parser.add_argument("--mutation-pack-summary", required=True)
    parser.add_argument("--mutation-real-runner-summary", required=True)
    parser.add_argument("--ledger", default="artifacts/private_model_mutation_scale_batch_v1/state/mutation_repro_depth_history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_mutation_repro_depth_history_ledger_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    guard = _load_json(args.mutation_repro_depth_guard_summary)
    pack = _load_json(args.mutation_pack_summary)
    realrun = _load_json(args.mutation_real_runner_summary)
    reasons: list[str] = []
    if not guard:
        reasons.append("mutation_repro_depth_guard_summary_missing")
    if not pack:
        reasons.append("mutation_pack_summary_missing")
    if not realrun:
        reasons.append("mutation_real_runner_summary_missing")

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    row = {
        "recorded_at_utc": now,
        "repro_depth_status": str(guard.get("status") or "UNKNOWN"),
        "tracked_models": _to_int(guard.get("tracked_models", 0)),
        "models_meeting_depth_threshold": _to_int(guard.get("models_meeting_depth_threshold", 0)),
        "models_meeting_depth_ratio_pct": _to_float(guard.get("models_meeting_depth_ratio_pct", 0.0)),
        "p10_reproducible_mutations_per_model": _to_float(guard.get("p10_reproducible_mutations_per_model", 0.0)),
        "max_model_share_pct": _to_float(guard.get("max_model_share_pct", 0.0)),
        "generated_mutations": _to_int(pack.get("total_mutations", 0)),
        "reproducible_mutations": _to_int(realrun.get("executed_count", 0)),
        "reproducibility_ratio_pct": _ratio(
            _to_int(realrun.get("executed_count", 0)),
            max(1, _to_int(pack.get("total_mutations", 0))),
        ),
    }
    if not reasons:
        _append_jsonl(ledger_path, [row])

    rows = _load_jsonl(ledger_path)
    total_records = len(rows)
    latest = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) >= 2 else {}

    avg_depth_ratio = round(sum(_to_float(r.get("models_meeting_depth_ratio_pct", 0.0)) for r in rows) / max(1, total_records), 4)
    avg_p10_depth = round(sum(_to_float(r.get("p10_reproducible_mutations_per_model", 0.0)) for r in rows) / max(1, total_records), 4)
    avg_concentration = round(sum(_to_float(r.get("max_model_share_pct", 0.0)) for r in rows) / max(1, total_records), 4)

    delta_depth_ratio = round(
        _to_float(latest.get("models_meeting_depth_ratio_pct", 0.0)) - _to_float(previous.get("models_meeting_depth_ratio_pct", 0.0)),
        4,
    )
    delta_p10_depth = round(
        _to_float(latest.get("p10_reproducible_mutations_per_model", 0.0))
        - _to_float(previous.get("p10_reproducible_mutations_per_model", 0.0)),
        4,
    )
    delta_concentration = round(_to_float(latest.get("max_model_share_pct", 0.0)) - _to_float(previous.get("max_model_share_pct", 0.0)), 4)

    alerts: list[str] = []
    if str(latest.get("repro_depth_status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_repro_depth_guard_not_pass")
    if _to_float(latest.get("models_meeting_depth_ratio_pct", 0.0)) < 80.0:
        alerts.append("latest_depth_ratio_below_80pct")
    if _to_float(latest.get("max_model_share_pct", 0.0)) > 35.0:
        alerts.append("latest_concentration_above_35pct")
    if total_records >= 2 and delta_depth_ratio < 0:
        alerts.append("depth_ratio_decreasing")
    if total_records >= 2 and delta_p10_depth < 0:
        alerts.append("p10_depth_decreasing")
    if total_records >= 2 and delta_concentration > 0:
        alerts.append("concentration_increasing")

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
        "latest_tracked_models": latest.get("tracked_models"),
        "latest_models_meeting_depth_ratio_pct": latest.get("models_meeting_depth_ratio_pct"),
        "latest_p10_reproducible_mutations_per_model": latest.get("p10_reproducible_mutations_per_model"),
        "latest_max_model_share_pct": latest.get("max_model_share_pct"),
        "latest_reproducibility_ratio_pct": latest.get("reproducibility_ratio_pct"),
        "avg_models_meeting_depth_ratio_pct": avg_depth_ratio,
        "avg_p10_reproducible_mutations_per_model": avg_p10_depth,
        "avg_max_model_share_pct": avg_concentration,
        "delta_models_meeting_depth_ratio_pct": delta_depth_ratio,
        "delta_p10_reproducible_mutations_per_model": delta_p10_depth,
        "delta_max_model_share_pct": delta_concentration,
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
                "latest_models_meeting_depth_ratio_pct": payload.get("latest_models_meeting_depth_ratio_pct"),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
