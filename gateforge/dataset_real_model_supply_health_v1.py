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
        "# GateForge Real Model Supply Health v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- supply_health_score: `{payload.get('supply_health_score')}`",
        f"- accepted_real_models: `{payload.get('accepted_real_models')}`",
        f"- supply_gap_count: `{payload.get('supply_gap_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute real model supply health from intake, license, backlog, and yield signals")
    parser.add_argument("--real-model-intake-summary", required=True)
    parser.add_argument("--real-model-license-compliance-summary", required=True)
    parser.add_argument("--real-model-intake-backlog-summary", required=True)
    parser.add_argument("--real-model-failure-yield-summary", required=True)
    parser.add_argument("--min-accepted-real-models", type=int, default=3)
    parser.add_argument("--min-accepted-large-models", type=int, default=1)
    parser.add_argument("--max-intake-reject-rate-pct", type=float, default=45.0)
    parser.add_argument("--out", default="artifacts/dataset_real_model_supply_health_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    intake = _load_json(args.real_model_intake_summary)
    license_summary = _load_json(args.real_model_license_compliance_summary)
    backlog = _load_json(args.real_model_intake_backlog_summary)
    yield_summary = _load_json(args.real_model_failure_yield_summary)

    reasons: list[str] = []
    if not intake:
        reasons.append("real_model_intake_summary_missing")
    if not license_summary:
        reasons.append("real_model_license_compliance_summary_missing")
    if not backlog:
        reasons.append("real_model_intake_backlog_summary_missing")
    if not yield_summary:
        reasons.append("real_model_failure_yield_summary_missing")

    accepted = _to_int(intake.get("accepted_count", 0))
    scale_counts = intake.get("accepted_scale_counts") if isinstance(intake.get("accepted_scale_counts"), dict) else {}
    accepted_large = _to_int(intake.get("accepted_large_count", scale_counts.get("large", 0)))
    has_large_signal = "accepted_large_count" in intake or bool(scale_counts)
    reject_rate_pct = _to_float(intake.get("reject_rate_pct", 0.0))
    has_reject_rate_signal = "reject_rate_pct" in intake
    weekly_target_status = _status(intake.get("weekly_target_status"))
    p0 = _to_int(backlog.get("p0_count", 0))
    license_risk = _to_float(license_summary.get("license_risk_score", 0.0))
    yield_score = _to_float(yield_summary.get("effective_yield_score", 0.0))

    supply_health_score = round(
        max(
            0.0,
            min(
                100.0,
                (yield_score * 0.45)
                + (max(0, accepted) * 9.0)
                + (max(0, accepted_large) * 6.0)
                + (max(0.0, 100.0 - license_risk) * 0.25)
                - (p0 * 8.0)
                - (max(0.0, reject_rate_pct) * 0.15),
            ),
        ),
        2,
    )

    supply_gaps: list[str] = []
    if accepted < int(args.min_accepted_real_models):
        supply_gaps.append("accepted_real_models_below_target")
    if has_large_signal and accepted_large < int(args.min_accepted_large_models):
        supply_gaps.append("accepted_large_models_below_target")
    if p0 > 0:
        supply_gaps.append("p0_backlog_present")
    if license_risk >= 30.0:
        supply_gaps.append("license_risk_high")
    if yield_score < 55.0:
        supply_gaps.append("effective_yield_low")
    if has_reject_rate_signal and reject_rate_pct > float(args.max_intake_reject_rate_pct):
        supply_gaps.append("intake_reject_rate_high")
    if weekly_target_status not in {"UNKNOWN", "PASS"}:
        supply_gaps.append("intake_weekly_target_not_pass")

    alerts: list[str] = []
    if _status(intake.get("status")) in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("intake_not_pass")
    if _status(license_summary.get("status")) in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("license_not_pass")
    if _status(yield_summary.get("status")) in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("yield_not_pass")
    if weekly_target_status in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("intake_weekly_target_not_pass")
    if supply_health_score < 72.0:
        alerts.append("supply_health_score_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts or supply_gaps:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "supply_health_score": supply_health_score,
        "accepted_real_models": accepted,
        "accepted_large_models": accepted_large,
        "reject_rate_pct": reject_rate_pct,
        "weekly_target_status": weekly_target_status,
        "supply_gap_count": len(supply_gaps),
        "supply_gaps": supply_gaps,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "signals": {
            "license_risk_score": license_risk,
            "effective_yield_score": yield_score,
            "backlog_p0_count": p0,
            "accepted_large_count": accepted_large,
            "reject_rate_pct": reject_rate_pct,
            "weekly_target_status": weekly_target_status,
        },
        "sources": {
            "real_model_intake_summary": args.real_model_intake_summary,
            "real_model_license_compliance_summary": args.real_model_license_compliance_summary,
            "real_model_intake_backlog_summary": args.real_model_intake_backlog_summary,
            "real_model_failure_yield_summary": args.real_model_failure_yield_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "supply_health_score": supply_health_score, "supply_gap_count": len(supply_gaps)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
