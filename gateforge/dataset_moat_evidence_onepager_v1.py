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


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(round(v))
    return 0


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    metrics = payload.get("public_metrics") if isinstance(payload.get("public_metrics"), dict) else {}
    lines = [
        "# GateForge Moat Evidence Onepager v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- headline: `{payload.get('headline')}`",
        "",
        "## Public Metrics",
        "",
        f"- real_model_count: `{metrics.get('real_model_count')}`",
        f"- reproducible_mutation_count: `{metrics.get('reproducible_mutation_count')}`",
        f"- failure_distribution_stability_score: `{metrics.get('failure_distribution_stability_score')}`",
        f"- gateforge_vs_plain_ci_advantage_score: `{metrics.get('gateforge_vs_plain_ci_advantage_score')}`",
        "",
        "## This Week Focus",
        "",
    ]
    for item in payload.get("focus_next_week") if isinstance(payload.get("focus_next_week"), list) else []:
        lines.append(f"- `{item}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build one-page external moat evidence brief from weekly chain")
    parser.add_argument("--moat-weekly-summary", required=True)
    parser.add_argument("--moat-weekly-summary-history", required=True)
    parser.add_argument("--moat-weekly-summary-history-trend", required=True)
    parser.add_argument("--moat-repro-runbook-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_moat_evidence_onepager_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    weekly = _load_json(args.moat_weekly_summary)
    history = _load_json(args.moat_weekly_summary_history)
    trend = _load_json(args.moat_weekly_summary_history_trend)
    runbook = _load_json(args.moat_repro_runbook_summary)

    reasons: list[str] = []
    if not weekly:
        reasons.append("moat_weekly_summary_missing")
    if not history:
        reasons.append("moat_weekly_summary_history_missing")
    if not trend:
        reasons.append("moat_weekly_summary_history_trend_missing")
    if not runbook:
        reasons.append("moat_repro_runbook_summary_missing")

    kpis = weekly.get("kpis") if isinstance(weekly.get("kpis"), dict) else {}
    public_metrics = {
        "real_model_count": _to_int(kpis.get("real_model_count", 0)),
        "reproducible_mutation_count": _to_int(kpis.get("reproducible_mutation_count", 0)),
        "failure_distribution_stability_score": _to_float(kpis.get("failure_distribution_stability_score", 0.0)),
        "gateforge_vs_plain_ci_advantage_score": _to_int(kpis.get("gateforge_vs_plain_ci_advantage_score", 0)),
        "history_avg_stability_score": _to_float(history.get("avg_stability_score", 0.0)),
        "history_avg_advantage_score": _to_float(history.get("avg_advantage_score", 0.0)),
        "trend_delta_avg_stability_score": _to_float(
            ((trend.get("trend") or {}).get("delta_avg_stability_score")) if isinstance(trend.get("trend"), dict) else 0.0
        ),
    }

    headline = (
        f"GateForge weekly moat evidence: {public_metrics['real_model_count']} real models, "
        f"{public_metrics['reproducible_mutation_count']} reproducible mutations, "
        f"stability {public_metrics['failure_distribution_stability_score']:.1f}, "
        f"advantage {public_metrics['gateforge_vs_plain_ci_advantage_score']}"
    )

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif str(runbook.get("readiness") or "") != "READY":
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "headline": headline,
        "week_tag": weekly.get("week_tag"),
        "public_metrics": public_metrics,
        "focus_next_week": weekly.get("focus_next_week") if isinstance(weekly.get("focus_next_week"), list) else [],
        "repro_steps": runbook.get("repro_steps") if isinstance(runbook.get("repro_steps"), list) else [],
        "sources": {
            "moat_weekly_summary": args.moat_weekly_summary,
            "moat_weekly_summary_history": args.moat_weekly_summary_history,
            "moat_weekly_summary_history_trend": args.moat_weekly_summary_history_trend,
            "moat_repro_runbook_summary": args.moat_repro_runbook_summary,
        },
        "reasons": sorted(set(reasons)),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "week_tag": payload.get("week_tag")}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
