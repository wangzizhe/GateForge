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
        "# GateForge Moat External Claims Brief v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- publishable: `{payload.get('publishable')}`",
        f"- claim_confidence_score: `{payload.get('claim_confidence_score')}`",
        f"- claim_count: `{payload.get('claim_count')}`",
        "",
        "## Claims",
        "",
    ]
    claims = payload.get("claims") if isinstance(payload.get("claims"), list) else []
    if claims:
        for c in claims:
            lines.append(f"- `{c.get('claim_id')}`: {c.get('text')}")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build externally communicable moat claims brief from defensibility signals")
    parser.add_argument("--moat-defensibility-report-summary", required=True)
    parser.add_argument("--moat-defensibility-history-summary", required=True)
    parser.add_argument("--moat-defensibility-history-trend-summary", required=True)
    parser.add_argument("--moat-evidence-onepager-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_moat_external_claims_brief_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    report = _load_json(args.moat_defensibility_report_summary)
    history = _load_json(args.moat_defensibility_history_summary)
    trend = _load_json(args.moat_defensibility_history_trend_summary)
    onepager = _load_json(args.moat_evidence_onepager_summary)

    reasons: list[str] = []
    if not report:
        reasons.append("moat_defensibility_report_summary_missing")
    if not history:
        reasons.append("moat_defensibility_history_summary_missing")
    if not trend:
        reasons.append("moat_defensibility_history_trend_summary_missing")

    defensibility_score = _to_float(report.get("moat_defensibility_score", 0.0))
    streak = _to_int(history.get("publish_ready_streak", 0))
    avg_defensibility = _to_float(history.get("avg_defensibility_score", 0.0))
    trend_delta = _to_float((trend.get("trend") or {}).get("delta_avg_defensibility_score", 0.0))

    claims: list[dict] = [
        {
            "claim_id": "claim.defensibility.score",
            "text": f"Moat defensibility score is {defensibility_score:.1f}.",
            "value": defensibility_score,
        },
        {
            "claim_id": "claim.defensibility.streak",
            "text": f"Publish-ready defensibility streak is {streak}.",
            "value": streak,
        },
        {
            "claim_id": "claim.defensibility.avg",
            "text": f"Average defensibility score is {avg_defensibility:.1f}.",
            "value": avg_defensibility,
        },
    ]

    if onepager:
        public = onepager.get("public_metrics") if isinstance(onepager.get("public_metrics"), dict) else {}
        claims.append(
            {
                "claim_id": "claim.evidence.public_metrics",
                "text": (
                    f"Public evidence shows {public.get('real_model_count')} real models, "
                    f"{public.get('reproducible_mutation_count')} reproducible mutations, "
                    f"stability {public.get('failure_distribution_stability_score')}."
                ),
                "value": public,
            }
        )

    claim_confidence_score = round(
        max(
            0.0,
            min(
                100.0,
                defensibility_score * 0.45
                + min(100.0, avg_defensibility) * 0.25
                + min(100.0, streak * 20.0) * 0.2
                + max(0.0, 50.0 + trend_delta * 20.0) * 0.1,
            ),
        ),
        2,
    )

    alerts: list[str] = []
    if _status(report.get("status")) != "PASS":
        alerts.append("defensibility_report_not_pass")
    if _status(history.get("status")) != "PASS":
        alerts.append("defensibility_history_not_pass")
    if _status(trend.get("status")) != "PASS":
        alerts.append("defensibility_history_trend_not_pass")
    if claim_confidence_score < 75.0:
        alerts.append("claim_confidence_low")

    publishable = bool(not alerts and claim_confidence_score >= 75.0)

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "publishable": publishable,
        "claim_confidence_score": claim_confidence_score,
        "claim_count": len(claims),
        "claims": claims,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "moat_defensibility_report_summary": args.moat_defensibility_report_summary,
            "moat_defensibility_history_summary": args.moat_defensibility_history_summary,
            "moat_defensibility_history_trend_summary": args.moat_defensibility_history_trend_summary,
            "moat_evidence_onepager_summary": args.moat_evidence_onepager_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "publishable": publishable, "claim_confidence_score": claim_confidence_score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
