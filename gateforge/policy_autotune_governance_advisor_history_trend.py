from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    trend = payload.get("trend", {})
    lines = [
        "# GateForge Policy Auto-Tune Governance Advisor Trend",
        "",
        f"- status: `{payload.get('status')}`",
        f"- delta_tighten_rate: `{trend.get('delta_tighten_rate')}`",
        f"- delta_rollback_review_rate: `{trend.get('delta_rollback_review_rate')}`",
        f"- delta_pairwise_patch_rate: `{trend.get('delta_pairwise_patch_rate')}`",
        f"- delta_leaderboard_instability_rate: `{trend.get('delta_leaderboard_instability_rate')}`",
        f"- delta_top_driver_non_null_rate: `{trend.get('delta_top_driver_non_null_rate')}`",
        f"- dominant_top_driver_previous: `{trend.get('dominant_top_driver_previous')}`",
        f"- dominant_top_driver_current: `{trend.get('dominant_top_driver_current')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = trend.get("alerts", [])
    if isinstance(alerts, list) and alerts:
        for a in alerts:
            lines.append(f"- `{a}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare autotune governance advisor history summaries and emit trend")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/policy_autotune_governance_advisor_history/trend.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)

    d_tighten = round(_to_float(current.get("tighten_rate")) - _to_float(previous.get("tighten_rate")), 4)
    d_rollback = round(
        _to_float(current.get("rollback_review_rate")) - _to_float(previous.get("rollback_review_rate")), 4
    )
    d_pairwise_patch = round(
        _to_float(current.get("pairwise_patch_rate")) - _to_float(previous.get("pairwise_patch_rate")), 4
    )
    d_leaderboard_instability = round(
        _to_float(current.get("leaderboard_instability_rate"))
        - _to_float(previous.get("leaderboard_instability_rate")),
        4,
    )
    d_top_driver_non_null = round(
        _to_float(current.get("top_driver_non_null_rate")) - _to_float(previous.get("top_driver_non_null_rate")),
        4,
    )

    current_distribution = current.get("top_driver_distribution") if isinstance(current.get("top_driver_distribution"), dict) else {}
    previous_distribution = (
        previous.get("top_driver_distribution") if isinstance(previous.get("top_driver_distribution"), dict) else {}
    )

    def _dominant(distribution: dict) -> str | None:
        if not distribution:
            return None
        items = sorted(distribution.items(), key=lambda kv: int(kv[1]), reverse=True)
        return str(items[0][0]) if items else None

    dominant_current = _dominant(current_distribution)
    dominant_previous = _dominant(previous_distribution)

    alerts: list[str] = []
    if d_tighten > 0:
        alerts.append("tighten_rate_increasing")
    if d_rollback > 0:
        alerts.append("rollback_review_rate_increasing")
    if d_pairwise_patch > 0:
        alerts.append("pairwise_patch_rate_increasing")
    if d_leaderboard_instability > 0:
        alerts.append("leaderboard_instability_rate_increasing")
    if d_top_driver_non_null > 0:
        alerts.append("top_driver_signal_coverage_increasing")
    if dominant_current and dominant_previous and dominant_current != dominant_previous:
        alerts.append("dominant_top_driver_changed")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    payload = {
        "status": status,
        "trend": {
            "delta_tighten_rate": d_tighten,
            "delta_rollback_review_rate": d_rollback,
            "delta_pairwise_patch_rate": d_pairwise_patch,
            "delta_leaderboard_instability_rate": d_leaderboard_instability,
            "delta_top_driver_non_null_rate": d_top_driver_non_null,
            "dominant_top_driver_previous": dominant_previous,
            "dominant_top_driver_current": dominant_current,
            "alerts": alerts,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))


if __name__ == "__main__":
    main()
