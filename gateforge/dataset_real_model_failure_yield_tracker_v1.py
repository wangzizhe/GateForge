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


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _extract_accepted_models(ledger: dict) -> list[str]:
    rows = ledger.get("records") if isinstance(ledger.get("records"), list) else []
    out: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("decision") or "") != "ACCEPT":
            continue
        model_id = str(row.get("model_id") or "").strip()
        if model_id:
            out.append(model_id)
    return sorted(set(out))


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Failure Yield Tracker v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- accepted_model_count: `{payload.get('accepted_model_count')}`",
        f"- executed_mutations: `{payload.get('executed_mutations')}`",
        f"- yield_per_accepted_model: `{payload.get('yield_per_accepted_model')}`",
        f"- execution_ratio_pct: `{payload.get('matrix_execution_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Track failure-yield productivity for accepted real Modelica models")
    parser.add_argument("--real-model-intake-ledger", required=True)
    parser.add_argument("--mutation-execution-matrix-summary", required=True)
    parser.add_argument("--replay-observation-store-summary", default=None)
    parser.add_argument("--min-yield-per-accepted-model", type=float, default=1.0)
    parser.add_argument("--min-matrix-execution-ratio-pct", type=float, default=60.0)
    parser.add_argument("--out", default="artifacts/dataset_real_model_failure_yield_tracker_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    ledger = _load_json(args.real_model_intake_ledger)
    matrix = _load_json(args.mutation_execution_matrix_summary)
    replay = _load_json(args.replay_observation_store_summary)

    reasons: list[str] = []
    if not ledger:
        reasons.append("real_model_intake_ledger_missing")
    if not matrix:
        reasons.append("mutation_execution_matrix_summary_missing")

    accepted_models = _extract_accepted_models(ledger)
    accepted_count = len(accepted_models)
    executed_mutations = int(matrix.get("executed_mutations", 0) or 0)
    total_mutations = int(matrix.get("total_mutations", 0) or 0)
    matrix_ratio = float(matrix.get("matrix_execution_ratio_pct", _ratio(executed_mutations, total_mutations)) or 0.0)
    replay_records = int(replay.get("ingested_records", replay.get("total_store_records", 0)) or 0)

    yield_per_accepted = round(executed_mutations / accepted_count, 2) if accepted_count > 0 else 0.0
    replay_to_execution_ratio = _ratio(replay_records, executed_mutations) if executed_mutations > 0 else 0.0

    alerts: list[str] = []
    if accepted_count == 0:
        alerts.append("no_accepted_real_models")
    if yield_per_accepted < float(args.min_yield_per_accepted_model):
        alerts.append("yield_per_accepted_model_below_threshold")
    if matrix_ratio < float(args.min_matrix_execution_ratio_pct):
        alerts.append("matrix_execution_ratio_below_threshold")
    if replay_records > 0 and replay_to_execution_ratio < 50.0:
        alerts.append("replay_record_density_low")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "accepted_model_count": accepted_count,
        "accepted_model_ids": accepted_models,
        "executed_mutations": executed_mutations,
        "total_mutations": total_mutations,
        "yield_per_accepted_model": yield_per_accepted,
        "matrix_execution_ratio_pct": matrix_ratio,
        "replay_record_count": replay_records,
        "replay_to_execution_ratio_pct": replay_to_execution_ratio,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "real_model_intake_ledger": args.real_model_intake_ledger,
            "mutation_execution_matrix_summary": args.mutation_execution_matrix_summary,
            "replay_observation_store_summary": args.replay_observation_store_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "yield_per_accepted_model": yield_per_accepted, "accepted_model_count": accepted_count}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
