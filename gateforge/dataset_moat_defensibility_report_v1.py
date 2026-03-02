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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _status(v: object) -> str:
    return str(v or "UNKNOWN")


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Moat Defensibility Report v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- moat_defensibility_score: `{payload.get('moat_defensibility_score')}`",
        f"- defensibility_band: `{payload.get('defensibility_band')}`",
        f"- key_alert_count: `{payload.get('key_alert_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build defensibility report from moat hard evidence components")
    parser.add_argument("--modelica-representativeness-gate-summary", required=True)
    parser.add_argument("--modelica-asset-uniqueness-index-summary", required=True)
    parser.add_argument("--mutation-depth-pressure-history-summary", required=True)
    parser.add_argument("--failure-distribution-stability-history-trend-summary", required=True)
    parser.add_argument("--moat-hard-evidence-plan-summary", required=True)
    parser.add_argument("--moat-weekly-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_moat_defensibility_report_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    represent = _load_json(args.modelica_representativeness_gate_summary)
    unique = _load_json(args.modelica_asset_uniqueness_index_summary)
    depth_hist = _load_json(args.mutation_depth_pressure_history_summary)
    stability = _load_json(args.failure_distribution_stability_history_trend_summary)
    plan = _load_json(args.moat_hard_evidence_plan_summary)
    weekly = _load_json(args.moat_weekly_summary)

    reasons: list[str] = []
    if not represent:
        reasons.append("modelica_representativeness_gate_summary_missing")
    if not unique:
        reasons.append("modelica_asset_uniqueness_index_summary_missing")
    if not depth_hist:
        reasons.append("mutation_depth_pressure_history_summary_missing")
    if not stability:
        reasons.append("failure_distribution_stability_history_trend_summary_missing")
    if not plan:
        reasons.append("moat_hard_evidence_plan_summary_missing")

    represent_score = _to_float(represent.get("representativeness_score", 0.0))
    unique_score = _to_float(unique.get("asset_uniqueness_index", 0.0))
    avg_pressure = _to_float(depth_hist.get("avg_pressure_index", 100.0))
    trend = stability.get("trend") if isinstance(stability.get("trend"), dict) else {}
    delta_stability = _to_float(trend.get("delta_avg_stability_score", 0.0))
    delta_drift = _to_float(trend.get("delta_avg_distribution_drift_score", 0.0))
    execution_focus = _to_float(plan.get("execution_focus_score", 0.0))

    weekly_bonus = 0.0
    if weekly:
        if _status(weekly.get("status")) == "PASS":
            weekly_bonus = 4.0
        elif _status(weekly.get("status")) == "NEEDS_REVIEW":
            weekly_bonus = 1.0

    stability_component = max(0.0, min(100.0, 55.0 + delta_stability * 8.0 - delta_drift * 40.0))

    moat_defensibility_score = round(
        max(
            0.0,
            min(
                100.0,
                represent_score * 0.28
                + unique_score * 0.24
                + max(0.0, 100.0 - avg_pressure) * 0.2
                + stability_component * 0.14
                + execution_focus * 0.14
                + weekly_bonus,
            ),
        ),
        2,
    )

    key_alerts: list[str] = []
    if represent_score < 70.0:
        key_alerts.append("representativeness_below_target")
    if unique_score < 80.0:
        key_alerts.append("asset_uniqueness_below_target")
    if avg_pressure > 35.0:
        key_alerts.append("mutation_depth_pressure_high")
    if delta_stability < 0:
        key_alerts.append("stability_trend_worsening")
    if delta_drift > 0.02:
        key_alerts.append("distribution_drift_worsening")
    if execution_focus < 65.0:
        key_alerts.append("execution_focus_low")

    defensibility_band = "HIGH"
    if moat_defensibility_score < 78.0:
        defensibility_band = "MEDIUM"
    if moat_defensibility_score < 62.0:
        defensibility_band = "LOW"

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif key_alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "moat_defensibility_score": moat_defensibility_score,
        "defensibility_band": defensibility_band,
        "key_alert_count": len(key_alerts),
        "key_alerts": key_alerts,
        "signals": {
            "representativeness_score": represent_score,
            "asset_uniqueness_index": unique_score,
            "avg_pressure_index": avg_pressure,
            "delta_avg_stability_score": delta_stability,
            "delta_avg_distribution_drift_score": delta_drift,
            "execution_focus_score": execution_focus,
            "weekly_status": _status(weekly.get("status")) if weekly else "UNKNOWN",
        },
        "reasons": sorted(set(reasons)),
        "sources": {
            "modelica_representativeness_gate_summary": args.modelica_representativeness_gate_summary,
            "modelica_asset_uniqueness_index_summary": args.modelica_asset_uniqueness_index_summary,
            "mutation_depth_pressure_history_summary": args.mutation_depth_pressure_history_summary,
            "failure_distribution_stability_history_trend_summary": args.failure_distribution_stability_history_trend_summary,
            "moat_hard_evidence_plan_summary": args.moat_hard_evidence_plan_summary,
            "moat_weekly_summary": args.moat_weekly_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "moat_defensibility_score": moat_defensibility_score, "defensibility_band": defensibility_band}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
