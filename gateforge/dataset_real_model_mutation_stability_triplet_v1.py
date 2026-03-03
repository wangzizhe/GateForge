from __future__ import annotations

import argparse
import json
import statistics
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
        s = line.strip()
        if not s:
            continue
        try:
            row = json.loads(s)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
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


def _round(v: float) -> float:
    return round(v, 4)


def _pct_range(values: list[float]) -> float:
    if not values:
        return 0.0
    lo = min(values)
    hi = max(values)
    base = max(1.0, statistics.fmean(values))
    return _round((hi - lo) / base * 100.0)


def _cv_pct(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = statistics.fmean(values)
    if mean == 0:
        return 0.0
    stdev = statistics.pstdev(values) if len(values) > 1 else 0.0
    return _round(stdev / mean * 100.0)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Mutation Stability Triplet v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- window_size: `{payload.get('window_size')}`",
        f"- accepted_models_cv_pct: `{payload.get('accepted_models_cv_pct')}`",
        f"- accepted_large_models_cv_pct: `{payload.get('accepted_large_models_cv_pct')}`",
        f"- generated_mutations_cv_pct: `{payload.get('generated_mutations_cv_pct')}`",
        f"- reproducibility_ratio_min_pct: `{payload.get('reproducibility_ratio_min_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Track 3-run stability for real-model + mutation depth outputs")
    parser.add_argument("--record-scale-summary", action="append", default=[])
    parser.add_argument("--record-uniqueness-summary", action="append", default=[])
    parser.add_argument("--ledger", default="artifacts/dataset_real_model_mutation_stability_triplet_v1/history.jsonl")
    parser.add_argument("--window-size", type=int, default=3)
    parser.add_argument("--max-accepted-models-cv-pct", type=float, default=3.0)
    parser.add_argument("--max-accepted-large-models-cv-pct", type=float, default=4.0)
    parser.add_argument("--max-generated-mutations-cv-pct", type=float, default=3.0)
    parser.add_argument("--min-reproducibility-ratio-pct", type=float, default=99.0)
    parser.add_argument("--out", default="artifacts/dataset_real_model_mutation_stability_triplet_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)

    scale_paths = [x for x in args.record_scale_summary if str(x).strip()]
    uniq_paths = [x for x in args.record_uniqueness_summary if str(x).strip()]
    append_rows: list[dict] = []

    for idx, scale_path in enumerate(scale_paths):
        scale = _load_json(scale_path)
        uniq = _load_json(uniq_paths[idx] if idx < len(uniq_paths) else None)
        if not scale:
            continue
        append_rows.append(
            {
                "recorded_at_utc": now,
                "scale_summary_path": scale_path,
                "uniqueness_summary_path": uniq_paths[idx] if idx < len(uniq_paths) else None,
                "bundle_status": str(scale.get("bundle_status") or "UNKNOWN"),
                "scale_gate_status": str(scale.get("scale_gate_status") or "UNKNOWN"),
                "accepted_models": _to_int(scale.get("accepted_models", 0)),
                "accepted_large_models": _to_int(scale.get("accepted_large_models", 0)),
                "generated_mutations": _to_int(scale.get("generated_mutations", 0)),
                "reproducible_mutations": _to_int(scale.get("reproducible_mutations", 0)),
                "mutations_per_failure_type": _to_int(scale.get("mutations_per_failure_type", 0)),
                "reproducibility_ratio_pct": _round(
                    100.0
                    * _to_int(scale.get("reproducible_mutations", 0))
                    / max(1, _to_int(scale.get("generated_mutations", 0)))
                ),
                "unique_accepted_models": _to_int(uniq.get("effective_unique_accepted_models", scale.get("accepted_models", 0))),
                "duplicate_ratio_pct": _to_float(uniq.get("duplicate_ratio_pct", 0.0)),
                "uniqueness_status": str(uniq.get("status") or "UNKNOWN"),
            }
        )

    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    window_size = max(1, int(args.window_size))
    window_rows = rows[-window_size:]

    reasons: list[str] = []
    if not rows:
        reasons.append("stability_ledger_empty")

    accepted = [_to_float(r.get("accepted_models", 0.0)) for r in window_rows]
    accepted_large = [_to_float(r.get("accepted_large_models", 0.0)) for r in window_rows]
    generated = [_to_float(r.get("generated_mutations", 0.0)) for r in window_rows]
    reproducibility = [_to_float(r.get("reproducibility_ratio_pct", 0.0)) for r in window_rows]
    duplicates = [_to_float(r.get("duplicate_ratio_pct", 0.0)) for r in window_rows]

    accepted_cv = _cv_pct(accepted)
    accepted_large_cv = _cv_pct(accepted_large)
    generated_cv = _cv_pct(generated)
    reproducibility_min = _round(min(reproducibility) if reproducibility else 0.0)
    duplicate_ratio_max = _round(max(duplicates) if duplicates else 0.0)

    alerts: list[str] = []
    if len(window_rows) < window_size:
        alerts.append("stability_window_not_full")
    if accepted_cv > float(args.max_accepted_models_cv_pct):
        alerts.append("accepted_models_cv_above_threshold")
    if accepted_large_cv > float(args.max_accepted_large_models_cv_pct):
        alerts.append("accepted_large_models_cv_above_threshold")
    if generated_cv > float(args.max_generated_mutations_cv_pct):
        alerts.append("generated_mutations_cv_above_threshold")
    if reproducibility_min < float(args.min_reproducibility_ratio_pct):
        alerts.append("reproducibility_ratio_below_threshold")
    if duplicate_ratio_max > 2.0:
        alerts.append("duplicate_ratio_above_2pct")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": now,
        "status": status,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": len(rows),
        "window_size": len(window_rows),
        "accepted_models_cv_pct": accepted_cv,
        "accepted_large_models_cv_pct": accepted_large_cv,
        "generated_mutations_cv_pct": generated_cv,
        "accepted_models_range_pct": _pct_range(accepted),
        "accepted_large_models_range_pct": _pct_range(accepted_large),
        "generated_mutations_range_pct": _pct_range(generated),
        "reproducibility_ratio_min_pct": reproducibility_min,
        "duplicate_ratio_max_pct": duplicate_ratio_max,
        "latest_record": window_rows[-1] if window_rows else {},
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "window_size": payload.get("window_size"),
                "accepted_models_cv_pct": accepted_cv,
                "generated_mutations_cv_pct": generated_cv,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
