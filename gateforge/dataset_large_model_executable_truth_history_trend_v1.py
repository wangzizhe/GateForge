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
        "# GateForge Large Model Executable Truth History Trend v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        f"- delta_large_executable_real_count: `{trend.get('delta_large_executable_real_count')}`",
        f"- delta_large_executable_real_rate_pct: `{trend.get('delta_large_executable_real_rate_pct')}`",
        f"- delta_large_model_check_pass_rate_pct: `{trend.get('delta_large_model_check_pass_rate_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare large-model executable truth history summaries and emit trend")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/dataset_large_model_executable_truth_history_ledger_v1/trend.json")
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
        "delta_large_executable_real_count": _to_int(current.get("latest_large_executable_real_count", 0))
        - _to_int(previous.get("latest_large_executable_real_count", 0)),
        "delta_large_executable_real_rate_pct": round(
            _to_float(current.get("latest_large_executable_real_rate_pct", 0.0))
            - _to_float(previous.get("latest_large_executable_real_rate_pct", 0.0)),
            4,
        ),
        "delta_large_model_check_pass_rate_pct": round(
            _to_float(current.get("latest_large_model_check_pass_rate_pct", 0.0))
            - _to_float(previous.get("latest_large_model_check_pass_rate_pct", 0.0)),
            4,
        ),
    }

    alerts: list[str] = []
    if trend["status_transition"] in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("large_model_truth_status_worsened")
    if trend["delta_large_executable_real_count"] < 0:
        alerts.append("large_executable_real_count_decreasing")
    if trend["delta_large_executable_real_rate_pct"] < 0:
        alerts.append("large_executable_real_rate_decreasing")
    if trend["delta_large_model_check_pass_rate_pct"] < 0:
        alerts.append("large_model_check_pass_rate_decreasing")

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
