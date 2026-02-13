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


def _compute_summary(repair: dict, review: dict, matrix: dict) -> dict:
    repair_compare = repair.get("profile_compare", {}) if isinstance(repair, dict) else {}
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

    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a governance snapshot from repair/review/matrix summaries")
    parser.add_argument("--repair-batch-summary", default=None, help="Path to repair_batch summary JSON")
    parser.add_argument("--review-ledger-summary", default=None, help="Path to review_ledger summary JSON")
    parser.add_argument("--ci-matrix-summary", default=None, help="Path to ci matrix summary JSON")
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
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)

    print(json.dumps({"status": summary.get("status"), "risks": summary.get("risks", [])}))
    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
