from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
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


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _append_jsonl(path: str, record: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Governance Promote Apply",
        "",
        f"- final_status: `{summary.get('final_status')}`",
        f"- apply_action: `{summary.get('apply_action')}`",
        f"- actor: `{summary.get('actor')}`",
        f"- compare_status: `{summary.get('compare_status')}`",
        f"- best_profile: `{summary.get('best_profile')}`",
        f"- best_decision: `{summary.get('best_decision')}`",
        f"- best_reason: `{summary.get('best_reason')}`",
        f"- ranking_selection_priority: `{','.join(summary.get('ranking_selection_priority') or [])}`",
        f"- recommended_profile: `{summary.get('recommended_profile')}`",
        f"- review_ticket_id: `{summary.get('review_ticket_id')}`",
        f"- require_ranking_explanation: `{summary.get('require_ranking_explanation')}`",
        f"- require_min_top_score_margin: `{summary.get('require_min_top_score_margin')}`",
        f"- audit_path: `{summary.get('audit_path')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = summary.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        lines.extend([f"- `{r}`" for r in reasons])
    else:
        lines.append("- `none`")
    lines.extend(
        [
            "",
            "## Ranking Explanation (Best vs Others)",
            "",
        ]
    )
    best_vs_others = summary.get("ranking_best_vs_others", [])
    if isinstance(best_vs_others, list) and best_vs_others:
        for row in best_vs_others:
            lines.append(
                f"- winner=`{row.get('winner_profile')}` challenger=`{row.get('challenger_profile')}` "
                f"margin=`{row.get('score_margin')}` tie_on_total=`{row.get('tie_on_total_score')}` "
                f"advantages=`{','.join(row.get('winner_advantages') or []) or 'none'}`"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _is_valid_ranking_explanation_items(best_vs_others: object) -> bool:
    if not isinstance(best_vs_others, list) or not best_vs_others:
        return False
    for row in best_vs_others:
        if not isinstance(row, dict):
            return False
        winner = row.get("winner_profile")
        challenger = row.get("challenger_profile")
        margin = row.get("score_margin")
        if not isinstance(winner, str) or not winner.strip():
            return False
        if not isinstance(challenger, str) or not challenger.strip():
            return False
        if not isinstance(margin, int):
            return False
    return True


def _evaluate(
    compare_payload: dict,
    review_ticket_id: str | None,
    *,
    require_ranking_explanation: bool,
    require_min_top_score_margin: int | None,
) -> dict:
    compare_status = str(compare_payload.get("status") or "UNKNOWN").upper()
    best_profile = compare_payload.get("best_profile")
    best_decision = str(compare_payload.get("best_decision") or "UNKNOWN").upper()
    recommended_profile = compare_payload.get("recommended_profile")
    reasons: list[str] = []

    if compare_status == "FAIL":
        return {
            "final_status": "FAIL",
            "apply_action": "block",
            "reasons": ["compare_status_fail"],
            "compare_status": compare_status,
            "best_profile": best_profile,
            "best_decision": best_decision,
            "recommended_profile": recommended_profile,
        }

    if compare_status == "NEEDS_REVIEW":
        if not isinstance(review_ticket_id, str) or not review_ticket_id.strip():
            return {
                "final_status": "FAIL",
                "apply_action": "block",
                "reasons": ["needs_review_ticket_required"],
                "compare_status": compare_status,
                "best_profile": best_profile,
                "best_decision": best_decision,
                "recommended_profile": recommended_profile,
            }
        return {
            "final_status": "NEEDS_REVIEW",
            "apply_action": "hold_for_review",
            "reasons": [],
            "compare_status": compare_status,
            "best_profile": best_profile,
            "best_decision": best_decision,
            "recommended_profile": recommended_profile,
        }

    if compare_status == "PASS":
        ranking_explanations = compare_payload.get("decision_explanations", {}).get("best_vs_others")
        if require_ranking_explanation:
            if not _is_valid_ranking_explanation_items(ranking_explanations):
                reasons.append("ranking_explanation_required")
        if isinstance(require_min_top_score_margin, int):
            margin = compare_payload.get("top_score_margin")
            if not isinstance(margin, int):
                reasons.append("top_score_margin_missing_when_required")
            elif margin < require_min_top_score_margin:
                reasons.append("top_score_margin_below_required")
        if not isinstance(best_profile, str) or not best_profile.strip():
            reasons.append("best_profile_missing")
        if best_decision not in {"PASS", "NEEDS_REVIEW", "FAIL"}:
            reasons.append("best_decision_invalid")
        if reasons:
            return {
                "final_status": "FAIL",
                "apply_action": "block",
                "reasons": reasons,
                "compare_status": compare_status,
                "best_profile": best_profile,
                "best_decision": best_decision,
                "recommended_profile": recommended_profile,
            }
        return {
            "final_status": "PASS",
            "apply_action": "promote",
            "reasons": [],
            "compare_status": compare_status,
            "best_profile": best_profile,
            "best_decision": best_decision,
            "recommended_profile": recommended_profile,
        }

    return {
        "final_status": "FAIL",
        "apply_action": "block",
        "reasons": ["compare_status_unknown"],
        "compare_status": compare_status,
        "best_profile": best_profile,
        "best_decision": best_decision,
        "recommended_profile": recommended_profile,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply governance promotion decision from promote-compare summary")
    parser.add_argument("--compare-summary", required=True, help="Path to governance_promote_compare summary JSON")
    parser.add_argument("--review-ticket-id", default=None, help="Required when compare summary status is NEEDS_REVIEW")
    parser.add_argument("--actor", default="governance.bot", help="Actor identity for audit record")
    parser.add_argument(
        "--require-ranking-explanation",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When enabled, PASS compare summaries must include decision_explanations.best_vs_others",
    )
    parser.add_argument(
        "--require-min-top-score-margin",
        type=int,
        default=None,
        help="When set, PASS compare summaries must include top_score_margin >= this value",
    )
    parser.add_argument("--out", default="artifacts/governance_promote_apply/summary.json", help="Output summary JSON")
    parser.add_argument("--report", default=None, help="Output markdown path")
    parser.add_argument(
        "--audit",
        default="artifacts/governance_promote_apply/decision_audit.jsonl",
        help="Append-only JSONL audit log path",
    )
    args = parser.parse_args()

    compare_payload = _load_json(args.compare_summary)
    evaluated = _evaluate(
        compare_payload,
        args.review_ticket_id,
        require_ranking_explanation=bool(args.require_ranking_explanation),
        require_min_top_score_margin=args.require_min_top_score_margin,
    )
    recorded_at = datetime.now(timezone.utc).isoformat()

    summary = {
        **evaluated,
        "actor": args.actor,
        "review_ticket_id": args.review_ticket_id,
        "require_ranking_explanation": bool(args.require_ranking_explanation),
        "require_min_top_score_margin": args.require_min_top_score_margin,
        "compare_summary_path": args.compare_summary,
        "constraint_reason": compare_payload.get("constraint_reason"),
        "top_score_margin": compare_payload.get("top_score_margin"),
        "min_top_score_margin": compare_payload.get("min_top_score_margin"),
        "best_total_score": compare_payload.get("best_total_score"),
        "best_reason": compare_payload.get("best_reason"),
        "ranking_selection_priority": compare_payload.get("decision_explanations", {}).get("selection_priority"),
        "ranking_best_vs_others": compare_payload.get("decision_explanations", {}).get("best_vs_others"),
        "recorded_at_utc": recorded_at,
        "audit_path": args.audit,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)

    audit_record = {
        "recorded_at_utc": recorded_at,
        "actor": args.actor,
        "final_status": summary["final_status"],
        "apply_action": summary["apply_action"],
        "reasons": summary.get("reasons", []),
        "compare_summary_path": args.compare_summary,
        "compare_status": summary.get("compare_status"),
        "best_profile": summary.get("best_profile"),
        "best_decision": summary.get("best_decision"),
        "recommended_profile": summary.get("recommended_profile"),
        "review_ticket_id": summary.get("review_ticket_id"),
        "require_ranking_explanation": summary.get("require_ranking_explanation"),
        "require_min_top_score_margin": summary.get("require_min_top_score_margin"),
        "constraint_reason": summary.get("constraint_reason"),
        "top_score_margin": summary.get("top_score_margin"),
        "min_top_score_margin": summary.get("min_top_score_margin"),
        "ranking_selection_priority": summary.get("ranking_selection_priority"),
        "ranking_best_vs_others": summary.get("ranking_best_vs_others"),
    }
    _append_jsonl(args.audit, audit_record)

    print(
        json.dumps(
            {
                "final_status": summary["final_status"],
                "apply_action": summary["apply_action"],
                "best_profile": summary.get("best_profile"),
            }
        )
    )
    if summary["final_status"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
