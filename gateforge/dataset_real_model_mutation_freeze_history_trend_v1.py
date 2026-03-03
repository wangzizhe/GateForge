from __future__ import annotations

import argparse
import json
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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    trend = payload.get("trend") if isinstance(payload.get("trend"), dict) else {}
    lines = [
        "# GateForge Freeze History Trend v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        f"- latest_freeze_status_transition: `{trend.get('latest_freeze_status_transition')}`",
        f"- delta_avg_accepted_models: `{trend.get('delta_avg_accepted_models')}`",
        f"- delta_avg_generated_mutations: `{trend.get('delta_avg_generated_mutations')}`",
        f"- delta_avg_validation_type_match_rate_pct: `{trend.get('delta_avg_validation_type_match_rate_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare freeze history summaries and emit trend deltas")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/dataset_real_model_mutation_freeze_history_ledger_v1/trend.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)

    reasons: list[str] = []
    if not current:
        reasons.append("current_summary_missing")
    if not previous:
        reasons.append("previous_summary_missing")

    trend = {
        "status_transition": f"{previous.get('status', 'UNKNOWN')}->{current.get('status', 'UNKNOWN')}",
        "latest_freeze_status_transition": (
            f"{previous.get('latest_freeze_status', 'UNKNOWN')}->{current.get('latest_freeze_status', 'UNKNOWN')}"
        ),
        "delta_avg_accepted_models": round(
            _to_float(current.get("avg_accepted_models")) - _to_float(previous.get("avg_accepted_models")),
            4,
        ),
        "delta_avg_generated_mutations": round(
            _to_float(current.get("avg_generated_mutations")) - _to_float(previous.get("avg_generated_mutations")),
            4,
        ),
        "delta_avg_reproducible_mutations": round(
            _to_float(current.get("avg_reproducible_mutations")) - _to_float(previous.get("avg_reproducible_mutations")),
            4,
        ),
        "delta_avg_canonical_net_growth_models": round(
            _to_float(current.get("avg_canonical_net_growth_models"))
            - _to_float(previous.get("avg_canonical_net_growth_models")),
            4,
        ),
        "delta_avg_validation_type_match_rate_pct": round(
            _to_float(current.get("avg_validation_type_match_rate_pct"))
            - _to_float(previous.get("avg_validation_type_match_rate_pct")),
            4,
        ),
        "delta_needs_review_rate": round(
            _to_float(current.get("needs_review_rate")) - _to_float(previous.get("needs_review_rate")),
            4,
        ),
    }

    alerts: list[str] = []
    if trend["status_transition"] in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("freeze_history_status_worsened")
    if trend["latest_freeze_status_transition"] in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("latest_freeze_status_worsened")
    if trend["delta_avg_accepted_models"] < 0:
        alerts.append("avg_accepted_models_decreasing")
    if trend["delta_avg_generated_mutations"] < 0:
        alerts.append("avg_generated_mutations_decreasing")
    if trend["delta_avg_reproducible_mutations"] < 0:
        alerts.append("avg_reproducible_mutations_decreasing")
    if trend["delta_avg_canonical_net_growth_models"] < 0:
        alerts.append("avg_canonical_net_growth_decreasing")
    if trend["delta_avg_validation_type_match_rate_pct"] < 0:
        alerts.append("avg_validation_type_match_decreasing")
    if trend["delta_needs_review_rate"] > 0:
        alerts.append("needs_review_rate_increasing")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "status": status,
        "trend": {**trend, "alerts": alerts},
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "current": args.current,
            "previous": args.previous,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
