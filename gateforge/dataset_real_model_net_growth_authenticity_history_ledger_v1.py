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
        "# GateForge Real Model Net Growth Authenticity History Ledger v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_net_new_unique_models: `{payload.get('latest_net_new_unique_models')}`",
        f"- latest_true_growth_ratio_pct: `{payload.get('latest_true_growth_ratio_pct')}`",
        f"- latest_suspected_duplicate_ratio_pct: `{payload.get('latest_suspected_duplicate_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append net-growth authenticity history and emit summary")
    parser.add_argument("--net-growth-authenticity-summary", required=True)
    parser.add_argument("--canonical-registry-summary", required=True)
    parser.add_argument("--intake-runner-summary", required=True)
    parser.add_argument("--ledger", default="artifacts/private_model_mutation_scale_batch_v1/state/net_growth_authenticity_history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_real_model_net_growth_authenticity_history_ledger_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    gate = _load_json(args.net_growth_authenticity_summary)
    canonical = _load_json(args.canonical_registry_summary)
    runner = _load_json(args.intake_runner_summary)
    reasons: list[str] = []
    if not gate:
        reasons.append("net_growth_authenticity_summary_missing")
    if not canonical:
        reasons.append("canonical_registry_summary_missing")
    if not runner:
        reasons.append("intake_runner_summary_missing")

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    row = {
        "recorded_at_utc": now,
        "gate_status": str(gate.get("status") or "UNKNOWN"),
        "canonical_new_models": _to_int(gate.get("canonical_new_models", 0)),
        "net_new_unique_models": _to_int(gate.get("net_new_unique_models", 0)),
        "true_growth_ratio_pct": _to_float(gate.get("true_growth_ratio_pct", 0.0)),
        "suspected_duplicate_ratio_pct": _to_float(gate.get("suspected_duplicate_ratio_pct", 0.0)),
        "canonical_total_models": _to_int(canonical.get("canonical_total_models", 0)),
        "accepted_models": _to_int(runner.get("accepted_count", 0)),
    }
    if not reasons:
        _append_jsonl(ledger_path, [row])

    rows = _load_jsonl(ledger_path)
    total_records = len(rows)
    latest = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) >= 2 else {}
    avg_true_growth = round(sum(_to_float(r.get("true_growth_ratio_pct", 0.0)) for r in rows) / max(1, total_records), 4)
    avg_suspected_dup = round(sum(_to_float(r.get("suspected_duplicate_ratio_pct", 0.0)) for r in rows) / max(1, total_records), 4)
    delta_net_new_unique = _to_int(latest.get("net_new_unique_models", 0)) - _to_int(previous.get("net_new_unique_models", 0))
    delta_true_growth = round(_to_float(latest.get("true_growth_ratio_pct", 0.0)) - _to_float(previous.get("true_growth_ratio_pct", 0.0)), 4)

    alerts: list[str] = []
    if str(latest.get("gate_status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_net_growth_authenticity_gate_not_pass")
    if _to_int(latest.get("net_new_unique_models", 0)) <= 0:
        alerts.append("latest_net_new_unique_models_zero")
    if _to_float(latest.get("true_growth_ratio_pct", 0.0)) < 70.0:
        alerts.append("latest_true_growth_ratio_below_70pct")
    if total_records >= 2 and delta_net_new_unique < 0:
        alerts.append("net_new_unique_models_decreasing")
    if total_records >= 2 and delta_true_growth < 0:
        alerts.append("true_growth_ratio_decreasing")

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
        "latest_net_new_unique_models": latest.get("net_new_unique_models"),
        "latest_true_growth_ratio_pct": latest.get("true_growth_ratio_pct"),
        "latest_suspected_duplicate_ratio_pct": latest.get("suspected_duplicate_ratio_pct"),
        "avg_true_growth_ratio_pct": avg_true_growth,
        "avg_suspected_duplicate_ratio_pct": avg_suspected_dup,
        "delta_net_new_unique_models": delta_net_new_unique,
        "delta_true_growth_ratio_pct": delta_true_growth,
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
                "latest_net_new_unique_models": payload.get("latest_net_new_unique_models"),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
