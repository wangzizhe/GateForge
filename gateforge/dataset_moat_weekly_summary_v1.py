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
    kpis = payload.get("kpis") if isinstance(payload.get("kpis"), dict) else {}
    lines = [
        "# GateForge Moat Weekly Summary v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- week_tag: `{payload.get('week_tag')}`",
        "",
        "## KPI Snapshot",
        "",
        f"- real_model_count: `{kpis.get('real_model_count')}`",
        f"- reproducible_mutation_count: `{kpis.get('reproducible_mutation_count')}`",
        f"- failure_distribution_stability_score: `{kpis.get('failure_distribution_stability_score')}`",
        f"- gateforge_vs_plain_ci_advantage_score: `{kpis.get('gateforge_vs_plain_ci_advantage_score')}`",
        "",
        "## Focus Next Week",
        "",
    ]
    focus = payload.get("focus_next_week") if isinstance(payload.get("focus_next_week"), list) else []
    if focus:
        for row in focus:
            lines.append(f"- `{row}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build single weekly moat summary from fixed evidence outputs")
    parser.add_argument("--week-tag", required=True)
    parser.add_argument("--moat-scorecard-baseline-summary", required=True)
    parser.add_argument("--model-asset-inventory-report-summary", required=True)
    parser.add_argument("--failure-distribution-baseline-freeze-summary", required=True)
    parser.add_argument("--moat-repro-runbook-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_moat_weekly_summary_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    scorecard = _load_json(args.moat_scorecard_baseline_summary)
    inventory = _load_json(args.model_asset_inventory_report_summary)
    freeze = _load_json(args.failure_distribution_baseline_freeze_summary)
    runbook = _load_json(args.moat_repro_runbook_summary)

    reasons: list[str] = []
    if not scorecard:
        reasons.append("moat_scorecard_baseline_summary_missing")
    if not inventory:
        reasons.append("model_asset_inventory_report_summary_missing")
    if not freeze:
        reasons.append("failure_distribution_baseline_freeze_summary_missing")
    if not runbook:
        reasons.append("moat_repro_runbook_summary_missing")

    indicators = scorecard.get("indicators") if isinstance(scorecard.get("indicators"), dict) else {}
    expected = runbook.get("expected_signals") if isinstance(runbook.get("expected_signals"), dict) else {}
    by_scale = inventory.get("by_scale") if isinstance(inventory.get("by_scale"), dict) else {}
    locked = freeze.get("locked_metrics") if isinstance(freeze.get("locked_metrics"), dict) else {}

    kpis = {
        "real_model_count": _to_int(indicators.get("real_model_count", expected.get("real_model_count", inventory.get("total_models", 0)))),
        "reproducible_mutation_count": _to_int(
            indicators.get("reproducible_mutation_count", expected.get("reproducible_mutation_count", 0))
        ),
        "failure_type_coverage_score": _to_float(indicators.get("failure_type_coverage_score", 0.0)),
        "failure_distribution_stability_score": _to_float(
            indicators.get("failure_distribution_stability_score", locked.get("failure_distribution_stability_score", 0.0))
        ),
        "gateforge_vs_plain_ci_advantage_score": _to_int(
            indicators.get("gateforge_vs_plain_ci_advantage_score", expected.get("gateforge_vs_plain_ci_advantage_score", 0))
        ),
        "large_model_count": _to_int(by_scale.get("large", 0)),
        "freeze_id": freeze.get("freeze_id"),
        "baseline_id": scorecard.get("baseline_id"),
        "runbook_readiness": runbook.get("readiness"),
    }

    focus_next_week: list[str] = []
    if kpis["real_model_count"] < 10:
        focus_next_week.append("increase_real_model_count")
    if kpis["large_model_count"] < 2:
        focus_next_week.append("increase_large_model_count")
    if kpis["failure_distribution_stability_score"] < 85.0:
        focus_next_week.append("stabilize_failure_distribution_delta")
    if kpis["gateforge_vs_plain_ci_advantage_score"] <= 0:
        focus_next_week.append("recover_gateforge_advantage_signal")
    if str(kpis.get("runbook_readiness") or "") != "READY":
        focus_next_week.append("close_runbook_readiness_gaps")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif focus_next_week:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "week_tag": args.week_tag,
        "kpis": kpis,
        "focus_next_week": focus_next_week,
        "sources": {
            "moat_scorecard_baseline_summary": args.moat_scorecard_baseline_summary,
            "model_asset_inventory_report_summary": args.model_asset_inventory_report_summary,
            "failure_distribution_baseline_freeze_summary": args.failure_distribution_baseline_freeze_summary,
            "moat_repro_runbook_summary": args.moat_repro_runbook_summary,
        },
        "reasons": sorted(set(reasons)),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "week_tag": args.week_tag, "focus_count": len(focus_next_week)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
