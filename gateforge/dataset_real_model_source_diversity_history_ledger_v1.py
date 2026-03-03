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
        "# GateForge Real Model Source Diversity History Ledger v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_unique_source_buckets: `{payload.get('latest_unique_source_buckets')}`",
        f"- latest_max_source_bucket_share_pct: `{payload.get('latest_max_source_bucket_share_pct')}`",
        f"- latest_unique_source_buckets_for_large_models: `{payload.get('latest_unique_source_buckets_for_large_models')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append real model source diversity history and emit summary")
    parser.add_argument("--source-diversity-guard-summary", required=True)
    parser.add_argument("--asset-discovery-summary", required=True)
    parser.add_argument("--intake-runner-summary", required=True)
    parser.add_argument("--ledger", default="artifacts/private_model_mutation_scale_batch_v1/state/real_model_source_diversity_history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_real_model_source_diversity_history_ledger_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    guard = _load_json(args.source_diversity_guard_summary)
    discovery = _load_json(args.asset_discovery_summary)
    runner = _load_json(args.intake_runner_summary)
    reasons: list[str] = []
    if not guard:
        reasons.append("source_diversity_guard_summary_missing")
    if not discovery:
        reasons.append("asset_discovery_summary_missing")
    if not runner:
        reasons.append("intake_runner_summary_missing")

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    row = {
        "recorded_at_utc": now,
        "source_diversity_status": str(guard.get("status") or "UNKNOWN"),
        "unique_source_repos": _to_int(guard.get("unique_source_repos", 0)),
        "unique_source_buckets": _to_int(guard.get("unique_source_buckets", 0)),
        "unique_source_buckets_for_large_models": _to_int(guard.get("unique_source_buckets_for_large_models", 0)),
        "max_source_bucket_share_pct": _to_float(guard.get("max_source_bucket_share_pct", 0.0)),
        "discovered_models": _to_int(discovery.get("total_candidates", 0)),
        "accepted_models": _to_int(runner.get("accepted_count", 0)),
    }
    if not reasons:
        _append_jsonl(ledger_path, [row])

    rows = _load_jsonl(ledger_path)
    total_records = len(rows)
    latest = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) >= 2 else {}
    avg_unique_buckets = round(sum(_to_int(r.get("unique_source_buckets", 0)) for r in rows) / max(1, total_records), 4)
    avg_max_share = round(sum(_to_float(r.get("max_source_bucket_share_pct", 0.0)) for r in rows) / max(1, total_records), 4)
    delta_unique_buckets = _to_int(latest.get("unique_source_buckets", 0)) - _to_int(previous.get("unique_source_buckets", 0))
    delta_max_share = round(
        _to_float(latest.get("max_source_bucket_share_pct", 0.0)) - _to_float(previous.get("max_source_bucket_share_pct", 0.0)),
        4,
    )

    alerts: list[str] = []
    if str(latest.get("source_diversity_status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_source_diversity_guard_not_pass")
    if _to_int(latest.get("unique_source_buckets", 0)) < 4:
        alerts.append("latest_unique_source_buckets_below_4")
    if _to_float(latest.get("max_source_bucket_share_pct", 0.0)) > 65.0:
        alerts.append("latest_max_source_bucket_share_above_65pct")
    if total_records >= 2 and delta_unique_buckets < 0:
        alerts.append("unique_source_buckets_decreasing")
    if total_records >= 2 and delta_max_share > 0:
        alerts.append("source_concentration_increasing")

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
        "latest_unique_source_buckets": latest.get("unique_source_buckets"),
        "latest_unique_source_buckets_for_large_models": latest.get("unique_source_buckets_for_large_models"),
        "latest_max_source_bucket_share_pct": latest.get("max_source_bucket_share_pct"),
        "avg_unique_source_buckets": avg_unique_buckets,
        "avg_max_source_bucket_share_pct": avg_max_share,
        "delta_unique_source_buckets": delta_unique_buckets,
        "delta_max_source_bucket_share_pct": delta_max_share,
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
                "latest_unique_source_buckets": payload.get("latest_unique_source_buckets"),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
