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


def _score(status: object) -> int:
    s = str(status or "").upper()
    if s == "PASS":
        return 2
    if s == "NEEDS_REVIEW":
        return 1
    if s == "FAIL":
        return 0
    return -1


def _load_optional_json(path: object) -> dict:
    if not isinstance(path, str) or not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _pairwise_net_margin(summary: dict) -> int | None:
    leaderboard = summary.get("decision_explanation_leaderboard")
    if isinstance(leaderboard, list) and leaderboard and isinstance(leaderboard[0], dict):
        value = leaderboard[0].get("pairwise_net_margin")
        if isinstance(value, int):
            return value
    return None


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Policy Auto-Tune Effectiveness",
        "",
        f"- decision: `{payload.get('decision')}`",
        f"- baseline_apply_status: `{payload.get('baseline_apply_status')}`",
        f"- tuned_apply_status: `{payload.get('tuned_apply_status')}`",
        f"- delta_apply_score: `{payload.get('delta_apply_score')}`",
        f"- baseline_compare_status: `{payload.get('baseline_compare_status')}`",
        f"- tuned_compare_status: `{payload.get('tuned_compare_status')}`",
        f"- delta_compare_score: `{payload.get('delta_compare_score')}`",
        f"- delta_top_score_margin: `{payload.get('delta_top_score_margin')}`",
        f"- delta_explanation_completeness: `{payload.get('delta_explanation_completeness')}`",
        f"- delta_pairwise_net_margin: `{payload.get('delta_pairwise_net_margin')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = payload.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        for r in reasons:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate effectiveness of policy autotune flow")
    parser.add_argument("--flow-summary", required=True)
    parser.add_argument("--out", default="artifacts/policy_autotune_governance/effectiveness.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    flow = _load_json(args.flow_summary)
    baseline = flow.get("baseline") if isinstance(flow.get("baseline"), dict) else {}
    tuned = flow.get("tuned") if isinstance(flow.get("tuned"), dict) else {}

    baseline_apply = baseline.get("apply_status")
    tuned_apply = tuned.get("apply_status")
    baseline_compare = baseline.get("compare_status")
    tuned_compare = tuned.get("compare_status")
    baseline_compare_summary = _load_optional_json(baseline.get("compare_path"))
    tuned_compare_summary = _load_optional_json(tuned.get("compare_path"))

    delta_apply = _score(tuned_apply) - _score(baseline_apply)
    delta_compare = _score(tuned_compare) - _score(baseline_compare)
    baseline_top_margin = baseline_compare_summary.get("top_score_margin")
    tuned_top_margin = tuned_compare_summary.get("top_score_margin")
    baseline_explanation = baseline_compare_summary.get("explanation_completeness")
    tuned_explanation = tuned_compare_summary.get("explanation_completeness")
    baseline_pairwise = _pairwise_net_margin(baseline_compare_summary)
    tuned_pairwise = _pairwise_net_margin(tuned_compare_summary)
    delta_top_margin = (
        int(tuned_top_margin) - int(baseline_top_margin)
        if isinstance(tuned_top_margin, int) and isinstance(baseline_top_margin, int)
        else None
    )
    delta_explanation = (
        int(tuned_explanation) - int(baseline_explanation)
        if isinstance(tuned_explanation, int) and isinstance(baseline_explanation, int)
        else None
    )
    delta_pairwise = (
        int(tuned_pairwise) - int(baseline_pairwise)
        if isinstance(tuned_pairwise, int) and isinstance(baseline_pairwise, int)
        else None
    )

    reasons: list[str] = []
    if delta_apply > 0:
        decision = "IMPROVED"
        reasons.append("apply_status_improved")
    elif delta_apply < 0:
        decision = "REGRESSED"
        reasons.append("apply_status_regressed")
    else:
        if delta_compare > 0:
            decision = "IMPROVED"
            reasons.append("compare_status_improved")
        elif delta_compare < 0:
            decision = "REGRESSED"
            reasons.append("compare_status_regressed")
        else:
            decision = "UNCHANGED"
            reasons.append("no_status_change")

    quality_regressed = any(
        isinstance(v, int) and v < 0 for v in (delta_top_margin, delta_explanation, delta_pairwise)
    )
    if decision == "UNCHANGED" and quality_regressed:
        decision = "REGRESSED"
        reasons.append("compare_quality_regressed")
    elif decision == "IMPROVED" and quality_regressed:
        reasons.append("improved_with_quality_tradeoff")

    payload = {
        "flow_summary_path": args.flow_summary,
        "decision": decision,
        "baseline_compare_status": baseline_compare,
        "tuned_compare_status": tuned_compare,
        "delta_compare_score": delta_compare,
        "baseline_apply_status": baseline_apply,
        "tuned_apply_status": tuned_apply,
        "delta_apply_score": delta_apply,
        "baseline_top_score_margin": baseline_top_margin,
        "tuned_top_score_margin": tuned_top_margin,
        "delta_top_score_margin": delta_top_margin,
        "baseline_explanation_completeness": baseline_explanation,
        "tuned_explanation_completeness": tuned_explanation,
        "delta_explanation_completeness": delta_explanation,
        "baseline_pairwise_net_margin": baseline_pairwise,
        "tuned_pairwise_net_margin": tuned_pairwise,
        "delta_pairwise_net_margin": delta_pairwise,
        "reasons": reasons,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"decision": decision, "delta_apply_score": delta_apply, "delta_compare_score": delta_compare}))


if __name__ == "__main__":
    main()
