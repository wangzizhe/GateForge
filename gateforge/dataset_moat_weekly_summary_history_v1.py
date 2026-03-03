from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        rows.append(json.loads(s))
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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(round(v))
    return 0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Moat Weekly Summary History v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_week_tag: `{payload.get('latest_week_tag')}`",
        f"- avg_real_model_count: `{payload.get('avg_real_model_count')}`",
        f"- avg_stability_score: `{payload.get('avg_stability_score')}`",
        f"- avg_advantage_score: `{payload.get('avg_advantage_score')}`",
        f"- avg_mutation_validation_fidelity_score: `{payload.get('avg_mutation_validation_fidelity_score')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append moat weekly summaries and emit compact history aggregates")
    parser.add_argument("--record", action="append", default=[])
    parser.add_argument("--ledger", default="artifacts/dataset_moat_weekly_summary_history_v1/history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_moat_weekly_summary_history_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)

    append_rows: list[dict] = []
    for path in args.record:
        payload = _load_json(path)
        kpis = payload.get("kpis") if isinstance(payload.get("kpis"), dict) else {}
        append_rows.append(
            {
                "recorded_at_utc": now,
                "source_record_path": path,
                "week_tag": str(payload.get("week_tag") or ""),
                "status": str(payload.get("status") or "UNKNOWN"),
                "real_model_count": _to_int(kpis.get("real_model_count", 0)),
                "reproducible_mutation_count": _to_int(kpis.get("reproducible_mutation_count", 0)),
                "failure_distribution_stability_score": round(_to_float(kpis.get("failure_distribution_stability_score", 0.0)), 2),
                "gateforge_vs_plain_ci_advantage_score": _to_int(kpis.get("gateforge_vs_plain_ci_advantage_score", 0)),
                "mutation_validation_fidelity_score": round(_to_float(kpis.get("mutation_validation_fidelity_score", 0.0)), 2),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}
    avg_real = round(sum(_to_float(r.get("real_model_count", 0.0)) for r in rows) / max(1, total), 4)
    avg_stability = round(sum(_to_float(r.get("failure_distribution_stability_score", 0.0)) for r in rows) / max(1, total), 4)
    avg_adv = round(sum(_to_float(r.get("gateforge_vs_plain_ci_advantage_score", 0.0)) for r in rows) / max(1, total), 4)
    avg_validation_fidelity = round(sum(_to_float(r.get("mutation_validation_fidelity_score", 0.0)) for r in rows) / max(1, total), 4)

    status = "PASS"
    alerts: list[str] = []
    if str(latest.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_weekly_summary_not_pass")
    if total >= 3 and avg_stability < 80.0:
        alerts.append("avg_stability_score_low")
    if total >= 3 and avg_adv <= 0.0:
        alerts.append("avg_gateforge_advantage_non_positive")
    if total >= 3 and avg_validation_fidelity < 60.0:
        alerts.append("avg_mutation_validation_fidelity_low")
    if alerts:
        status = "NEEDS_REVIEW"

    out = {
        "generated_at_utc": now,
        "status": status,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "latest_week_tag": latest.get("week_tag"),
        "latest_status": latest.get("status"),
        "avg_real_model_count": avg_real,
        "avg_stability_score": avg_stability,
        "avg_advantage_score": avg_adv,
        "avg_mutation_validation_fidelity_score": avg_validation_fidelity,
        "alerts": alerts,
    }
    _write_json(args.out, out)
    _write_markdown(args.report_out or _default_md_path(args.out), out)
    print(json.dumps({"status": status, "total_records": total, "avg_stability_score": avg_stability}))


if __name__ == "__main__":
    main()
