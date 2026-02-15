from __future__ import annotations

import argparse
import json
from pathlib import Path


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _status_from_signals(signals: dict) -> str:
    if signals.get("matrix_status") == "FAIL":
        return "FAIL"
    if signals.get("repair_compare_has_downgrade"):
        return "NEEDS_REVIEW"
    if signals.get("strict_non_pass_rate", 0.0) >= 0.5:
        return "NEEDS_REVIEW"
    return "PASS"


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _extract_repair_compare(repair: dict) -> dict:
    if not isinstance(repair, dict):
        return {}
    profile_compare = repair.get("profile_compare")
    if isinstance(profile_compare, dict):
        return profile_compare

    strategy_compare = repair.get("strategy_compare")
    if not isinstance(strategy_compare, dict):
        return {}

    relation = str(strategy_compare.get("relation") or "").lower()
    downgrade_count = 1 if relation == "downgraded" else 0
    strict_downgrade_rate = 1.0 if relation == "downgraded" else 0.0
    return {
        "from_policy_profile": strategy_compare.get("from_profile"),
        "to_policy_profile": strategy_compare.get("to_profile"),
        "downgrade_count": downgrade_count,
        "strict_downgrade_rate": strict_downgrade_rate,
        "strategy_compare_relation": strategy_compare.get("relation"),
    }


def _compute_trend(current: dict, previous: dict) -> dict:
    current_status = str(current.get("status") or "UNKNOWN")
    prev_status = str(previous.get("status") or "UNKNOWN")
    transition = f"{prev_status}->{current_status}"

    current_risks = set(r for r in current.get("risks", []) if isinstance(r, str))
    prev_risks = set(r for r in previous.get("risks", []) if isinstance(r, str))

    current_kpis = current.get("kpis", {}) if isinstance(current.get("kpis"), dict) else {}
    prev_kpis = previous.get("kpis", {}) if isinstance(previous.get("kpis"), dict) else {}

    return {
        "status_transition": transition,
        "new_risks": sorted(current_risks - prev_risks),
        "resolved_risks": sorted(prev_risks - current_risks),
        "kpi_delta": {
            "strict_downgrade_rate_delta": round(
                _to_float(current_kpis.get("strict_downgrade_rate")) - _to_float(prev_kpis.get("strict_downgrade_rate")),
                4,
            ),
            "review_recovery_rate_delta": round(
                _to_float(current_kpis.get("review_recovery_rate")) - _to_float(prev_kpis.get("review_recovery_rate")),
                4,
            ),
            "strict_non_pass_rate_delta": round(
                _to_float(current_kpis.get("strict_non_pass_rate")) - _to_float(prev_kpis.get("strict_non_pass_rate")),
                4,
            ),
            "approval_rate_delta": round(
                _to_float(current_kpis.get("approval_rate")) - _to_float(prev_kpis.get("approval_rate")),
                4,
            ),
            "fail_rate_delta": round(
                _to_float(current_kpis.get("fail_rate")) - _to_float(prev_kpis.get("fail_rate")),
                4,
            ),
        },
    }


def _compute_summary(repair: dict, review: dict, matrix: dict) -> dict:
    repair_compare = _extract_repair_compare(repair)
    kpis = review.get("kpis", {}) if isinstance(review, dict) else {}

    strict_non_pass_rate = float(kpis.get("strict_non_pass_rate", 0.0) or 0.0)
    review_recovery_rate = float(kpis.get("review_recovery_rate", 0.0) or 0.0)
    downgrade_count = int(repair_compare.get("downgrade_count", 0) or 0)

    signals = {
        "matrix_status": matrix.get("matrix_status", "UNKNOWN"),
        "repair_compare_has_downgrade": downgrade_count > 0,
        "strict_non_pass_rate": strict_non_pass_rate,
        "review_recovery_rate": review_recovery_rate,
    }

    status = _status_from_signals(signals)

    risks = []
    if signals["matrix_status"] == "FAIL":
        risks.append("ci_matrix_failed")
    if downgrade_count > 0:
        risks.append("strict_profile_downgrade_detected")
    if strict_non_pass_rate >= 0.5:
        risks.append("strict_non_pass_rate_high")
    if review_recovery_rate < 0.5:
        risks.append("review_recovery_rate_low")

    return {
        "status": status,
        "signals": signals,
        "kpis": {
            "strict_downgrade_rate": repair_compare.get("strict_downgrade_rate"),
            "downgrade_count": downgrade_count,
            "strategy_compare_relation": repair_compare.get("strategy_compare_relation"),
            "review_recovery_rate": review_recovery_rate,
            "strict_non_pass_rate": strict_non_pass_rate,
            "approval_rate": kpis.get("approval_rate"),
            "fail_rate": kpis.get("fail_rate"),
        },
        "policy_profiles": {
            "compare_from": repair_compare.get("from_policy_profile"),
            "compare_to": repair_compare.get("to_policy_profile"),
            "review_counts": review.get("policy_profile_counts", {}),
        },
        "sources": {
            "repair_batch_summary_path": repair.get("_source_path"),
            "review_ledger_summary_path": review.get("_source_path"),
            "ci_matrix_summary_path": matrix.get("_source_path"),
        },
        "risks": risks,
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    kpis = summary.get("kpis", {})
    lines = [
        "# GateForge Governance Snapshot",
        "",
        f"- status: `{summary.get('status')}`",
        f"- strict_downgrade_rate: `{kpis.get('strict_downgrade_rate')}`",
        f"- downgrade_count: `{kpis.get('downgrade_count')}`",
        f"- strategy_compare_relation: `{kpis.get('strategy_compare_relation')}`",
        f"- review_recovery_rate: `{kpis.get('review_recovery_rate')}`",
        f"- strict_non_pass_rate: `{kpis.get('strict_non_pass_rate')}`",
        f"- approval_rate: `{kpis.get('approval_rate')}`",
        f"- fail_rate: `{kpis.get('fail_rate')}`",
        "",
        "## Risks",
        "",
    ]
    risks = summary.get("risks", [])
    if risks:
        for r in risks:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Sources", ""])
    for k, v in summary.get("sources", {}).items():
        lines.append(f"- {k}: `{v}`")

    trend = summary.get("trend")
    if isinstance(trend, dict):
        lines.extend(
            [
                "",
                "## Trend vs Previous Snapshot",
                "",
                f"- status_transition: `{trend.get('status_transition')}`",
                "",
                "### New Risks",
                "",
            ]
        )
        new_risks = trend.get("new_risks", [])
        if new_risks:
            for r in new_risks:
                lines.append(f"- `{r}`")
        else:
            lines.append("- `none`")
        lines.extend(["", "### Resolved Risks", ""])
        resolved = trend.get("resolved_risks", [])
        if resolved:
            for r in resolved:
                lines.append(f"- `{r}`")
        else:
            lines.append("- `none`")
        lines.extend(["", "### KPI Delta", ""])
        delta = trend.get("kpi_delta", {})
        for k in sorted(delta.keys()):
            lines.append(f"- {k}: `{delta[k]}`")

    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a governance snapshot from repair/review/matrix summaries")
    parser.add_argument("--repair-batch-summary", default=None, help="Path to repair_batch summary JSON")
    parser.add_argument("--review-ledger-summary", default=None, help="Path to review_ledger summary JSON")
    parser.add_argument("--ci-matrix-summary", default=None, help="Path to ci matrix summary JSON")
    parser.add_argument("--previous-summary", default=None, help="Optional previous governance snapshot JSON")
    parser.add_argument("--out", default="artifacts/governance_snapshot/summary.json", help="Output JSON path")
    parser.add_argument("--report", default=None, help="Output markdown path")
    args = parser.parse_args()

    repair = _load_json(args.repair_batch_summary)
    review = _load_json(args.review_ledger_summary)
    matrix = _load_json(args.ci_matrix_summary)
    if args.repair_batch_summary:
        repair["_source_path"] = args.repair_batch_summary
    if args.review_ledger_summary:
        review["_source_path"] = args.review_ledger_summary
    if args.ci_matrix_summary:
        matrix["_source_path"] = args.ci_matrix_summary

    summary = _compute_summary(repair, review, matrix)
    if args.previous_summary:
        previous = _load_json(args.previous_summary)
        if previous:
            summary["trend"] = _compute_trend(summary, previous)
            summary["sources"]["previous_snapshot_path"] = args.previous_summary
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)

    print(json.dumps({"status": summary.get("status"), "risks": summary.get("risks", [])}))
    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
