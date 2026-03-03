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


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    trend = payload.get("trend") if isinstance(payload.get("trend"), dict) else {}
    lines = [
        "# GateForge Mutation Selection History Trend v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        f"- delta_selected_large_ratio_pct: `{trend.get('delta_selected_large_ratio_pct')}`",
        f"- delta_selected_family_coverage: `{trend.get('delta_selected_family_coverage')}`",
        f"- delta_max_family_share_pct: `{trend.get('delta_max_family_share_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare mutation selection history summaries and emit trend")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/dataset_mutation_selection_history_ledger_v1/trend.json")
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
        "delta_selected_large_ratio_pct": round(
            _to_float(current.get("latest_selected_large_ratio_pct", 0.0))
            - _to_float(previous.get("latest_selected_large_ratio_pct", 0.0)),
            4,
        ),
        "delta_selected_family_coverage": _to_int(current.get("latest_selected_families", 0))
        - _to_int(previous.get("latest_selected_families", 0)),
        "delta_selected_source_coverage": _to_int(current.get("latest_selected_source_buckets", 0))
        - _to_int(previous.get("latest_selected_source_buckets", 0)),
        "delta_max_family_share_pct": round(
            _to_float(current.get("latest_max_family_share_pct", 0.0))
            - _to_float(previous.get("latest_max_family_share_pct", 0.0)),
            4,
        ),
    }

    alerts: list[str] = []
    if trend["status_transition"] in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("selection_history_status_worsened")
    if trend["delta_selected_large_ratio_pct"] < 0:
        alerts.append("selected_large_ratio_decreasing")
    if trend["delta_selected_family_coverage"] < 0:
        alerts.append("selected_family_coverage_decreasing")
    if trend["delta_selected_source_coverage"] < 0:
        alerts.append("selected_source_coverage_decreasing")
    if trend["delta_max_family_share_pct"] > 0:
        alerts.append("family_concentration_increasing")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {"status": status, "trend": {**trend, "alerts": alerts}, "alerts": alerts, "reasons": sorted(set(reasons))}
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
