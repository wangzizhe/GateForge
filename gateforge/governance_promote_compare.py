from __future__ import annotations

import argparse
import json
import subprocess
import sys
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


def _decision_score(decision: str | None) -> int:
    value = str(decision or "").upper()
    if value == "PASS":
        return 2
    if value == "NEEDS_REVIEW":
        return 1
    if value == "FAIL":
        return 0
    return -1


def _score_row(
    row: dict,
    recommended_profile: str | None,
    *,
    decision_weight: int,
    exit_penalty: int,
    reason_penalty: int,
    recommended_bonus: int,
) -> dict:
    decision_score = _decision_score(row.get("decision"))
    exit_code = int(row.get("exit_code", 99))
    reasons = row.get("reasons", [])
    reasons_count = len(reasons) if isinstance(reasons, list) else 0

    decision_component = decision_score * decision_weight
    exit_component = 0 if exit_code == 0 else -abs(exit_penalty)
    reasons_component = -(reasons_count * abs(reason_penalty))
    recommended_component = (
        abs(recommended_bonus)
        if isinstance(recommended_profile, str) and row.get("profile") == recommended_profile
        else 0
    )
    total_score = decision_component + exit_component + reasons_component + recommended_component
    return {
        "decision_score": decision_score,
        "decision_component": decision_component,
        "exit_component": exit_component,
        "reasons_component": reasons_component,
        "recommended_component": recommended_component,
        "total_score": total_score,
        "reasons_count": reasons_count,
    }


def _run_promote(snapshot: str, profile: str, out_path: str, override_path: str | None) -> tuple[int, dict]:
    cmd = [
        sys.executable,
        "-m",
        "gateforge.governance_promote",
        "--snapshot",
        snapshot,
        "--profile",
        profile,
        "--out",
        out_path,
    ]
    if override_path:
        cmd.extend(["--override", override_path])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    payload = {}
    path = Path(out_path)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    return int(proc.returncode), payload


def _select_best_profile(results: list[dict], recommended_profile: str | None) -> tuple[str | None, str]:
    if not results:
        return None, "no_profiles"
    sorted_results = sorted(
        results,
        key=lambda x: (
            int(x.get("total_score", -999999)),
            _decision_score(x.get("decision")),
            -int(x.get("exit_code", 99)),
        ),
        reverse=True,
    )
    top_row = sorted_results[0]
    top_score = int(top_row.get("total_score", -999999))
    tied = [r for r in sorted_results if int(r.get("total_score", -999999)) == top_score]
    if recommended_profile:
        for row in tied:
            if row.get("profile") == recommended_profile:
                return str(row.get("profile")), "recommended_profile_preferred_within_top_total_score"
    return str(top_row.get("profile")), "highest_total_score"


def _score_advantages(winner: dict, challenger: dict) -> list[str]:
    winner_breakdown = winner.get("score_breakdown", {})
    challenger_breakdown = challenger.get("score_breakdown", {})
    if not isinstance(winner_breakdown, dict) or not isinstance(challenger_breakdown, dict):
        return []
    labels = [
        "decision_component",
        "exit_component",
        "reasons_component",
        "recommended_component",
    ]
    advantages: list[str] = []
    for label in labels:
        try:
            if int(winner_breakdown.get(label, 0)) > int(challenger_breakdown.get(label, 0)):
                advantages.append(label)
        except (TypeError, ValueError):
            continue
    return advantages


def _build_decision_explanations(
    ranking: list[dict],
    best_profile: str | None,
    best_reason: str,
) -> dict:
    if not ranking:
        return {
            "best_profile": best_profile,
            "best_reason": best_reason,
            "selection_priority": ["total_score", "decision", "exit_code", "recommended_profile_tiebreak"],
            "best_vs_others": [],
        }
    best_row = ranking[0]
    best_total_score = int(best_row.get("total_score", 0))
    comparisons = []
    for row in ranking[1:]:
        challenger_score = int(row.get("total_score", 0))
        tie_on_total = challenger_score == best_total_score
        comparisons.append(
            {
                "winner_profile": best_row.get("profile"),
                "challenger_profile": row.get("profile"),
                "winner_total_score": best_total_score,
                "challenger_total_score": challenger_score,
                "score_margin": best_total_score - challenger_score,
                "tie_on_total_score": tie_on_total,
                "winner_advantages": _score_advantages(best_row, row),
            }
        )
    return {
        "best_profile": best_profile,
        "best_reason": best_reason,
        "selection_priority": ["total_score", "decision", "exit_code", "recommended_profile_tiebreak"],
        "best_vs_others": comparisons,
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Governance Promote Compare",
        "",
        f"- status: `{summary.get('status')}`",
        f"- best_profile: `{summary.get('best_profile')}`",
        f"- best_reason: `{summary.get('best_reason')}`",
        f"- recommended_profile: `{summary.get('recommended_profile')}`",
        f"- recommended_profile_decision: `{summary.get('recommended_profile_decision')}`",
        f"- require_recommended_eligible: `{summary.get('require_recommended_eligible')}`",
        f"- constraint_reason: `{summary.get('constraint_reason')}`",
        f"- best_total_score: `{summary.get('best_total_score')}`",
        f"- top_score_margin: `{summary.get('top_score_margin')}`",
        f"- min_top_score_margin: `{summary.get('min_top_score_margin')}`",
        "",
        "## Decision Explanation",
        "",
        f"- decision_weight: `{summary.get('scoring', {}).get('decision_weight')}`",
        f"- exit_penalty: `{summary.get('scoring', {}).get('exit_penalty')}`",
        f"- reason_penalty: `{summary.get('scoring', {}).get('reason_penalty')}`",
        f"- recommended_bonus: `{summary.get('scoring', {}).get('recommended_bonus')}`",
        "",
        "Best profile score breakdown:",
        "",
    ]
    best_score = summary.get("best_score_breakdown", {})
    if isinstance(best_score, dict) and best_score:
        lines.extend(
            [
                f"- decision_component: `{best_score.get('decision_component')}`",
                f"- exit_component: `{best_score.get('exit_component')}`",
                f"- reasons_component: `{best_score.get('reasons_component')}`",
                f"- recommended_component: `{best_score.get('recommended_component')}`",
            ]
        )
    else:
        lines.append("- `none`")
    lines.extend(
        [
            "",
            "## Ranking",
            "",
        ]
    )
    for row in summary.get("ranking", []):
        lines.append(
            f"- rank={row.get('rank')} profile=`{row.get('profile')}` total_score=`{row.get('total_score')}` "
            f"decision=`{row.get('decision')}` exit_code=`{row.get('exit_code')}` reasons=`{row.get('reasons_count')}`"
        )
    lines.extend(
        [
            "",
            "## Ranking Explanation",
            "",
        ]
    )
    explanation = summary.get("decision_explanations", {})
    if isinstance(explanation, dict):
        lines.append(
            f"- selection_priority: `{','.join(explanation.get('selection_priority', []))}`"
        )
        for row in explanation.get("best_vs_others", []):
            lines.append(
                f"- winner=`{row.get('winner_profile')}` vs challenger=`{row.get('challenger_profile')}` "
                f"margin=`{row.get('score_margin')}` tie_on_total=`{row.get('tie_on_total_score')}` "
                f"advantages=`{','.join(row.get('winner_advantages', [])) or 'none'}`"
            )
    else:
        lines.append("- `none`")
    lines.extend(
        [
            "",
        "## Profile Results",
        "",
        ]
    )
    for row in summary.get("profile_results", []):
        lines.append(
            f"- {row.get('profile')}: decision=`{row.get('decision')}` exit_code=`{row.get('exit_code')}` "
            f"total_score=`{row.get('total_score')}` is_recommended=`{row.get('is_recommended')}` "
            f"override_path=`{row.get('override_path')}`"
        )
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare governance promote decisions across multiple profiles")
    parser.add_argument("--snapshot", required=True, help="Governance snapshot JSON path")
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["default", "industrial_strict"],
        help="Promotion profiles to compare",
    )
    parser.add_argument(
        "--override-map",
        default=None,
        help="Optional JSON mapping {profile: override_json_path}",
    )
    parser.add_argument(
        "--require-recommended-eligible",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When enabled, recommended profile must exist and not be FAIL",
    )
    parser.add_argument(
        "--score-decision-weight",
        type=int,
        default=100,
        help="Weight multiplier for decision score PASS/NEEDS_REVIEW/FAIL",
    )
    parser.add_argument(
        "--score-exit-penalty",
        type=int,
        default=5,
        help="Penalty when promote command exits non-zero",
    )
    parser.add_argument(
        "--score-reason-penalty",
        type=int,
        default=1,
        help="Penalty per reason item in profile result",
    )
    parser.add_argument(
        "--score-recommended-bonus",
        type=int,
        default=3,
        help="Bonus for row matching snapshot recommended_profile",
    )
    parser.add_argument(
        "--min-top-score-margin",
        type=int,
        default=0,
        help="If >0, top score minus second score must meet threshold; otherwise decision is NEEDS_REVIEW",
    )
    parser.add_argument(
        "--out-dir",
        default="artifacts/governance_promote_compare",
        help="Directory for per-profile outputs",
    )
    parser.add_argument("--out", default=None, help="Summary JSON path")
    parser.add_argument("--report", default=None, help="Summary markdown path")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_out = args.out or str(out_dir / "summary.json")
    report_out = args.report or _default_md_path(summary_out)

    snapshot_payload = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    kpis = snapshot_payload.get("kpis", {}) if isinstance(snapshot_payload.get("kpis"), dict) else {}
    recommended_profile = kpis.get("recommended_profile") if isinstance(kpis.get("recommended_profile"), str) else None
    override_map = {}
    if args.override_map:
        override_map = json.loads(Path(args.override_map).read_text(encoding="utf-8"))
        if not isinstance(override_map, dict):
            raise SystemExit("--override-map must contain a JSON object")

    results = []
    for profile in args.profiles:
        profile_out = out_dir / f"{profile}.json"
        profile_override = override_map.get(profile) if isinstance(override_map.get(profile), str) else None
        exit_code, payload = _run_promote(args.snapshot, profile, str(profile_out), profile_override)
        results.append(
            {
                "profile": profile,
                "decision": payload.get("decision"),
                "exit_code": exit_code,
                "out_path": str(profile_out),
                "override_path": profile_override,
                "is_recommended": bool(recommended_profile and profile == recommended_profile),
                "reasons": payload.get("reasons", []),
            }
        )

    for row in results:
        row["score_breakdown"] = _score_row(
            row,
            recommended_profile,
            decision_weight=args.score_decision_weight,
            exit_penalty=args.score_exit_penalty,
            reason_penalty=args.score_reason_penalty,
            recommended_bonus=args.score_recommended_bonus,
        )
        row["total_score"] = row["score_breakdown"]["total_score"]
        row["reasons_count"] = row["score_breakdown"]["reasons_count"]

    ranking = sorted(
        [
            {
                "profile": row.get("profile"),
                "decision": row.get("decision"),
                "exit_code": row.get("exit_code"),
                "total_score": row.get("total_score"),
                "reasons_count": row.get("reasons_count"),
                "score_breakdown": row.get("score_breakdown"),
            }
            for row in results
        ],
        key=lambda x: (
            int(x.get("total_score", -999999)),
            _decision_score(x.get("decision")),
            -int(x.get("exit_code", 99)),
        ),
        reverse=True,
    )
    for idx, row in enumerate(ranking, start=1):
        row["rank"] = idx

    top_score_margin = None
    if len(ranking) >= 2:
        top_score = int(ranking[0].get("total_score", 0))
        second_score = int(ranking[1].get("total_score", 0))
        top_score_margin = top_score - second_score

    best_profile, best_reason = _select_best_profile(results, recommended_profile)
    best_row = next((r for r in results if r.get("profile") == best_profile), None)
    best_decision = str(best_row.get("decision") if isinstance(best_row, dict) else "UNKNOWN")
    decision_explanations = _build_decision_explanations(ranking, best_profile, best_reason)

    status = "PASS"
    if all(str(r.get("decision")).upper() == "FAIL" for r in results):
        status = "FAIL"
    elif best_decision.upper() == "NEEDS_REVIEW":
        status = "NEEDS_REVIEW"

    recommended_row = next((r for r in results if r.get("profile") == recommended_profile), None)
    recommended_decision = str(recommended_row.get("decision")) if isinstance(recommended_row, dict) else None
    constraint_reason = None
    if args.require_recommended_eligible and recommended_profile:
        if recommended_row is None:
            status = "FAIL"
            constraint_reason = "recommended_profile_not_in_profiles"
        elif str(recommended_decision).upper() == "FAIL":
            status = "FAIL"
            constraint_reason = "recommended_profile_failed"
        elif str(recommended_decision).upper() == "NEEDS_REVIEW" and status == "PASS":
            status = "NEEDS_REVIEW"
            constraint_reason = "recommended_profile_needs_review"
    if (
        status == "PASS"
        and isinstance(top_score_margin, int)
        and args.min_top_score_margin > 0
        and top_score_margin < int(args.min_top_score_margin)
    ):
        status = "NEEDS_REVIEW"
        constraint_reason = "top_score_margin_low"

    summary = {
        "status": status,
        "snapshot_path": args.snapshot,
        "override_map_path": args.override_map,
        "recommended_profile": recommended_profile,
        "recommended_profile_decision": recommended_decision,
        "require_recommended_eligible": bool(args.require_recommended_eligible),
        "constraint_reason": constraint_reason,
        "best_profile": best_profile,
        "best_decision": best_decision,
        "best_reason": best_reason,
        "best_total_score": best_row.get("total_score") if isinstance(best_row, dict) else None,
        "best_score_breakdown": best_row.get("score_breakdown") if isinstance(best_row, dict) else {},
        "top_score_margin": top_score_margin,
        "min_top_score_margin": int(args.min_top_score_margin),
        "scoring": {
            "decision_weight": args.score_decision_weight,
            "exit_penalty": args.score_exit_penalty,
            "reason_penalty": args.score_reason_penalty,
            "recommended_bonus": args.score_recommended_bonus,
        },
        "decision_explanations": decision_explanations,
        "ranking": ranking,
        "profile_results": results,
    }
    _write_json(summary_out, summary)
    _write_markdown(report_out, summary)
    print(json.dumps({"status": status, "best_profile": best_profile, "best_decision": best_decision}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
