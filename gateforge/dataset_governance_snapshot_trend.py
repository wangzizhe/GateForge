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


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _compute_trend(current: dict, previous: dict) -> dict:
    current_status = str(current.get("status") or "UNKNOWN")
    previous_status = str(previous.get("status") or "UNKNOWN")
    current_risks = set(r for r in (current.get("risks") or []) if isinstance(r, str))
    previous_risks = set(r for r in (previous.get("risks") or []) if isinstance(r, str))
    current_kpis = current.get("kpis", {}) if isinstance(current.get("kpis"), dict) else {}
    previous_kpis = previous.get("kpis", {}) if isinstance(previous.get("kpis"), dict) else {}
    return {
        "status_transition": f"{previous_status}->{current_status}",
        "new_risks": sorted(current_risks - previous_risks),
        "resolved_risks": sorted(previous_risks - current_risks),
        "status_delta": {
            "dataset_promotion_effectiveness_history_trend_status_transition": (
                f"{previous_kpis.get('dataset_promotion_effectiveness_history_trend_status')}->"
                f"{current_kpis.get('dataset_promotion_effectiveness_history_trend_status')}"
            ),
            "dataset_promotion_effectiveness_history_latest_decision_transition": (
                f"{previous_kpis.get('dataset_promotion_effectiveness_history_latest_decision')}->"
                f"{current_kpis.get('dataset_promotion_effectiveness_history_latest_decision')}"
            ),
        },
        "kpi_delta": {
            "dataset_pipeline_deduplicated_cases_delta": round(
                _to_float(current_kpis.get("dataset_pipeline_deduplicated_cases"))
                - _to_float(previous_kpis.get("dataset_pipeline_deduplicated_cases")),
                4,
            ),
            "dataset_pipeline_failure_case_rate_delta": round(
                _to_float(current_kpis.get("dataset_pipeline_failure_case_rate"))
                - _to_float(previous_kpis.get("dataset_pipeline_failure_case_rate")),
                4,
            ),
            "dataset_governance_total_records_delta": round(
                _to_float(current_kpis.get("dataset_governance_total_records"))
                - _to_float(previous_kpis.get("dataset_governance_total_records")),
                4,
            ),
            "dataset_governance_trend_alert_count_delta": round(
                _to_float(current_kpis.get("dataset_governance_trend_alert_count"))
                - _to_float(previous_kpis.get("dataset_governance_trend_alert_count")),
                4,
            ),
        },
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    trend = summary.get("trend", {})
    lines = [
        "# GateForge Dataset Governance Snapshot Trend",
        "",
        f"- status: `{summary.get('status')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        "",
        "## New Risks",
        "",
    ]
    new_risks = trend.get("new_risks", [])
    if new_risks:
        for r in new_risks:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Resolved Risks", ""])
    resolved = trend.get("resolved_risks", [])
    if resolved:
        for r in resolved:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## KPI Delta", ""])
    for k, v in (trend.get("kpi_delta") or {}).items():
        lines.append(f"- {k}: `{v}`")
    lines.extend(["", "## Status Delta", ""])
    for k, v in (trend.get("status_delta") or {}).items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute trend between two dataset governance snapshots")
    parser.add_argument("--summary", required=True, help="Current dataset governance snapshot JSON path")
    parser.add_argument("--previous-summary", required=True, help="Previous dataset governance snapshot JSON path")
    parser.add_argument(
        "--out",
        default="artifacts/dataset_governance_snapshot_trend/summary.json",
        help="Output JSON path",
    )
    parser.add_argument("--report", default=None, help="Output markdown path")
    args = parser.parse_args()

    current = _load_json(args.summary)
    previous = _load_json(args.previous_summary)
    trend = _compute_trend(current, previous)
    summary = {
        **current,
        "trend": trend,
        "sources": {
            **(current.get("sources") if isinstance(current.get("sources"), dict) else {}),
            "previous_summary_path": args.previous_summary,
        },
    }
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "status_transition": trend.get("status_transition")}))
    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
