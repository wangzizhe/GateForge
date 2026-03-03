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
        "# GateForge Scale Batch History Ledger v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_bundle_status: `{payload.get('latest_bundle_status')}`",
        f"- avg_accepted_models: `{payload.get('avg_accepted_models')}`",
        f"- avg_generated_mutations: `{payload.get('avg_generated_mutations')}`",
        f"- avg_reproducible_mutations: `{payload.get('avg_reproducible_mutations')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append scale batch summaries into ledger and emit history KPIs")
    parser.add_argument("--record", action="append", default=[])
    parser.add_argument("--ledger", default="artifacts/private_model_mutation_scale_batch_v1/state/scale_history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_scale_batch_history_ledger_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    reasons: list[str] = []

    append_rows: list[dict] = []
    for record_path in args.record:
        payload = _load_json(record_path)
        if not payload:
            reasons.append(f"record_missing:{record_path}")
            continue
        append_rows.append(
            {
                "recorded_at_utc": now,
                "source_record_path": record_path,
                "bundle_status": str(payload.get("bundle_status") or "UNKNOWN"),
                "scale_gate_status": str(payload.get("scale_gate_status") or "UNKNOWN"),
                "hard_moat_gates_status": str(payload.get("hard_moat_gates_status") or "UNKNOWN"),
                "accepted_models": _to_int(payload.get("accepted_models", 0)),
                "generated_mutations": _to_int(payload.get("generated_mutations", 0)),
                "reproducible_mutations": _to_int(payload.get("reproducible_mutations", 0)),
                "canonical_total_models": _to_int(payload.get("canonical_total_models", 0)),
                "canonical_net_growth_models": _to_int(payload.get("canonical_net_growth_models", 0)),
                "hard_moat_hardness_score": round(_to_float(payload.get("hard_moat_hardness_score", 0.0)), 4),
            }
        )

    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) >= 2 else {}

    bundle_pass_count = len([r for r in rows if str(r.get("bundle_status") or "") == "PASS"])
    avg_accepted = round(sum(_to_int(r.get("accepted_models", 0)) for r in rows) / max(1, total), 4)
    avg_generated = round(sum(_to_int(r.get("generated_mutations", 0)) for r in rows) / max(1, total), 4)
    avg_reproducible = round(sum(_to_int(r.get("reproducible_mutations", 0)) for r in rows) / max(1, total), 4)
    avg_growth = round(sum(_to_int(r.get("canonical_net_growth_models", 0)) for r in rows) / max(1, total), 4)
    avg_hardness = round(sum(_to_float(r.get("hard_moat_hardness_score", 0.0)) for r in rows) / max(1, total), 4)

    delta_accepted = _to_int(latest.get("accepted_models", 0)) - _to_int(previous.get("accepted_models", 0))
    delta_generated = _to_int(latest.get("generated_mutations", 0)) - _to_int(previous.get("generated_mutations", 0))
    delta_reproducible = _to_int(latest.get("reproducible_mutations", 0)) - _to_int(previous.get("reproducible_mutations", 0))
    delta_canonical_total_models = _to_int(latest.get("canonical_total_models", 0)) - _to_int(previous.get("canonical_total_models", 0))

    alerts: list[str] = []
    if str(latest.get("bundle_status") or "") != "PASS":
        alerts.append("latest_bundle_status_not_pass")
    if str(latest.get("hard_moat_gates_status") or "") == "FAIL":
        alerts.append("latest_hard_moat_status_fail")
    if len(rows) >= 2 and delta_accepted < 0:
        alerts.append("accepted_models_decreasing")
    if len(rows) >= 2 and delta_generated < 0:
        alerts.append("generated_mutations_decreasing")
    if len(rows) >= 2 and delta_reproducible < 0:
        alerts.append("reproducible_mutations_decreasing")
    if total >= 3 and avg_growth <= 0:
        alerts.append("avg_canonical_net_growth_not_positive")

    status = "PASS"
    if reasons and not rows:
        status = "FAIL"
    elif alerts or reasons:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": now,
        "status": status,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "bundle_pass_rate": round(bundle_pass_count / max(1, total), 4),
        "latest_bundle_status": latest.get("bundle_status"),
        "latest_scale_gate_status": latest.get("scale_gate_status"),
        "latest_hard_moat_gates_status": latest.get("hard_moat_gates_status"),
        "latest_accepted_models": latest.get("accepted_models"),
        "latest_generated_mutations": latest.get("generated_mutations"),
        "latest_reproducible_mutations": latest.get("reproducible_mutations"),
        "latest_canonical_total_models": latest.get("canonical_total_models"),
        "latest_canonical_net_growth_models": latest.get("canonical_net_growth_models"),
        "latest_hard_moat_hardness_score": latest.get("hard_moat_hardness_score"),
        "avg_accepted_models": avg_accepted,
        "avg_generated_mutations": avg_generated,
        "avg_reproducible_mutations": avg_reproducible,
        "avg_canonical_net_growth_models": avg_growth,
        "avg_hard_moat_hardness_score": avg_hardness,
        "delta_accepted_models": delta_accepted,
        "delta_generated_mutations": delta_generated,
        "delta_reproducible_mutations": delta_reproducible,
        "delta_canonical_total_models": delta_canonical_total_models,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_records": total, "latest_bundle_status": payload["latest_bundle_status"]}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
