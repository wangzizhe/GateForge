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
        return int(v)
    return 0


def _status(v: object) -> str:
    return str(v or "UNKNOWN")


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Supply Pipeline v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- supply_pipeline_score: `{payload.get('supply_pipeline_score')}`",
        f"- new_models_30d: `{payload.get('new_models_30d')}`",
        f"- large_model_candidates_30d: `{payload.get('large_model_candidates_30d')}`",
        f"- license_blockers: `{payload.get('license_blockers')}`",
        f"- ready_for_intake_queue: `{payload.get('ready_for_intake_queue')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
    if alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build real-model supply pipeline dashboard from intake and governance signals")
    parser.add_argument("--real-model-intake-summary", required=True)
    parser.add_argument("--real-model-intake-backlog-summary", required=True)
    parser.add_argument("--real-model-license-compliance-summary", required=True)
    parser.add_argument("--real-model-growth-trend-summary", required=True)
    parser.add_argument("--min-new-models-30d", type=int, default=2)
    parser.add_argument("--min-large-model-candidates-30d", type=int, default=1)
    parser.add_argument("--max-license-blockers", type=int, default=0)
    parser.add_argument("--out", default="artifacts/dataset_real_model_supply_pipeline_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    intake = _load_json(args.real_model_intake_summary)
    backlog = _load_json(args.real_model_intake_backlog_summary)
    license_summary = _load_json(args.real_model_license_compliance_summary)
    growth = _load_json(args.real_model_growth_trend_summary)

    reasons: list[str] = []
    if not intake:
        reasons.append("real_model_intake_summary_missing")
    if not backlog:
        reasons.append("real_model_intake_backlog_summary_missing")
    if not license_summary:
        reasons.append("real_model_license_compliance_summary_missing")
    if not growth:
        reasons.append("real_model_growth_trend_summary_missing")

    accepted_count = _to_int(intake.get("accepted_count", 0))
    accepted_large_count = _to_int(intake.get("accepted_large_count", 0))
    reject_rate_pct = _to_float(intake.get("reject_rate_pct", 0.0))
    p0_count = _to_int(backlog.get("p0_count", 0))
    backlog_item_count = _to_int(backlog.get("backlog_item_count", 0))
    license_blockers = _to_int(license_summary.get("disallowed_license_count", 0))
    unknown_license_ratio = _to_float(license_summary.get("unknown_license_ratio_pct", 0.0))
    growth_delta_total = _to_int(growth.get("delta_total_real_models", 0))
    growth_delta_large = _to_int(growth.get("delta_large_models", 0))
    growth_velocity_score = _to_float(growth.get("growth_velocity_score", 0.0))

    new_models_30d = max(0, growth_delta_total)
    large_model_candidates_30d = max(0, growth_delta_large)
    ready_for_intake_queue = max(0, accepted_count - p0_count)

    supply_pipeline_score = round(
        max(
            0.0,
            min(
                100.0,
                (growth_velocity_score * 0.45)
                + (new_models_30d * 9.0)
                + (large_model_candidates_30d * 8.0)
                + (ready_for_intake_queue * 3.5)
                - (reject_rate_pct * 0.15)
                - (license_blockers * 12.0)
                - (unknown_license_ratio * 0.12)
                - (p0_count * 8.0),
            ),
        ),
        2,
    )

    alerts: list[str] = []
    if new_models_30d < int(args.min_new_models_30d):
        alerts.append("new_models_30d_below_target")
    if large_model_candidates_30d < int(args.min_large_model_candidates_30d):
        alerts.append("large_model_candidates_30d_below_target")
    if license_blockers > int(args.max_license_blockers):
        alerts.append("license_blockers_present")
    if p0_count > 0:
        alerts.append("intake_backlog_p0_present")
    if _status(intake.get("status")) in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("intake_status_not_pass")
    if _status(backlog.get("status")) in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("backlog_status_not_pass")
    if _status(license_summary.get("status")) in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("license_status_not_pass")
    if _status(growth.get("status")) in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("growth_status_not_pass")
    if supply_pipeline_score < 72.0:
        alerts.append("supply_pipeline_score_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "supply_pipeline_score": supply_pipeline_score,
        "new_models_30d": new_models_30d,
        "large_model_candidates_30d": large_model_candidates_30d,
        "license_blockers": license_blockers,
        "unknown_license_ratio_pct": unknown_license_ratio,
        "accepted_real_models": accepted_count,
        "accepted_large_models": accepted_large_count,
        "intake_reject_rate_pct": reject_rate_pct,
        "backlog_item_count": backlog_item_count,
        "intake_backlog_p0_count": p0_count,
        "ready_for_intake_queue": ready_for_intake_queue,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "real_model_intake_summary": args.real_model_intake_summary,
            "real_model_intake_backlog_summary": args.real_model_intake_backlog_summary,
            "real_model_license_compliance_summary": args.real_model_license_compliance_summary,
            "real_model_growth_trend_summary": args.real_model_growth_trend_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "supply_pipeline_score": supply_pipeline_score,
                "new_models_30d": new_models_30d,
                "large_model_candidates_30d": large_model_candidates_30d,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
