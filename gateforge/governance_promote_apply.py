from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROMOTE_APPLY_POLICY_DIR = Path("policies/promote_apply")


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


def _resolve_promote_apply_policy_path(policy_path: str | None, policy_profile: str | None) -> str:
    if policy_path and policy_profile:
        raise ValueError("Use either --policy-path or --policy-profile, not both")
    if policy_profile:
        profile = policy_profile if policy_profile.endswith(".json") else f"{policy_profile}.json"
        resolved = PROMOTE_APPLY_POLICY_DIR / profile
        if not resolved.exists():
            raise ValueError(f"Promote-apply policy profile not found: {resolved}")
        return str(resolved)
    if policy_path:
        return policy_path
    return str(PROMOTE_APPLY_POLICY_DIR / "default.json")


def _resolve_effective_guardrails(args: argparse.Namespace, policy_payload: dict) -> dict:
    rank_from_cli = args.require_ranking_explanation is not None
    margin_from_cli = args.require_min_top_score_margin is not None
    quality_from_cli = args.require_min_explanation_quality is not None

    require_ranking = (
        bool(args.require_ranking_explanation)
        if rank_from_cli
        else bool(policy_payload.get("require_ranking_explanation", False))
    )
    min_margin = (
        args.require_min_top_score_margin
        if margin_from_cli
        else policy_payload.get("require_min_top_score_margin")
    )
    min_quality = (
        args.require_min_explanation_quality
        if quality_from_cli
        else policy_payload.get("require_min_explanation_quality")
    )

    if min_margin is not None and not isinstance(min_margin, int):
        raise ValueError("effective require_min_top_score_margin must be int or null")
    if min_quality is not None and not isinstance(min_quality, int):
        raise ValueError("effective require_min_explanation_quality must be int or null")

    return {
        "require_ranking_explanation": require_ranking,
        "require_min_top_score_margin": min_margin,
        "require_min_explanation_quality": min_quality,
        "source_require_ranking_explanation": "cli" if rank_from_cli else "policy_profile",
        "source_require_min_top_score_margin": "cli" if margin_from_cli else "policy_profile",
        "source_require_min_explanation_quality": "cli" if quality_from_cli else "policy_profile",
    }


def _stable_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _baseline_effective_guardrails_hash(summary: dict) -> str | None:
    from_hash = summary.get("effective_guardrails_hash")
    if isinstance(from_hash, str) and from_hash:
        return from_hash
    baseline_effective = {
        "require_ranking_explanation": summary.get("require_ranking_explanation"),
        "require_min_top_score_margin": summary.get("require_min_top_score_margin"),
        "require_min_explanation_quality": summary.get("require_min_explanation_quality"),
    }
    if not isinstance(baseline_effective["require_ranking_explanation"], bool):
        return None
    if baseline_effective["require_min_top_score_margin"] is not None and not isinstance(
        baseline_effective["require_min_top_score_margin"], int
    ):
        return None
    if baseline_effective["require_min_explanation_quality"] is not None and not isinstance(
        baseline_effective["require_min_explanation_quality"], int
    ):
        return None
    return _stable_hash(baseline_effective)


def _detect_guardrail_drift(
    *,
    baseline_summary_path: str | None,
    current_policy_hash: str,
    current_effective_hash: str,
) -> dict:
    if not baseline_summary_path:
        return {
            "baseline_apply_summary_path": None,
            "baseline_policy_hash": None,
            "baseline_effective_guardrails_hash": None,
            "drift_reasons": [],
        }

    baseline_payload = _load_json(baseline_summary_path)
    baseline_policy_hash = baseline_payload.get("policy_hash")
    baseline_effective_hash = _baseline_effective_guardrails_hash(baseline_payload)
    reasons: list[str] = []
    if isinstance(baseline_policy_hash, str) and baseline_policy_hash and baseline_policy_hash != current_policy_hash:
        reasons.append("guardrail_policy_hash_drift")
    if isinstance(baseline_effective_hash, str) and baseline_effective_hash and baseline_effective_hash != current_effective_hash:
        reasons.append("guardrail_effective_guardrails_hash_drift")
    return {
        "baseline_apply_summary_path": baseline_summary_path,
        "baseline_policy_hash": baseline_policy_hash if isinstance(baseline_policy_hash, str) else None,
        "baseline_effective_guardrails_hash": baseline_effective_hash,
        "drift_reasons": reasons,
    }


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
        f"- policy_profile: `{summary.get('policy_profile')}`",
        f"- policy_version: `{summary.get('policy_version')}`",
        f"- policy_path: `{summary.get('policy_path')}`",
        f"- require_ranking_explanation: `{summary.get('require_ranking_explanation')}`",
        f"- source_require_ranking_explanation: `{summary.get('source_require_ranking_explanation')}`",
        f"- require_min_top_score_margin: `{summary.get('require_min_top_score_margin')}`",
        f"- source_require_min_top_score_margin: `{summary.get('source_require_min_top_score_margin')}`",
        f"- require_min_explanation_quality: `{summary.get('require_min_explanation_quality')}`",
        f"- source_require_min_explanation_quality: `{summary.get('source_require_min_explanation_quality')}`",
        f"- explanation_quality_score: `{summary.get('explanation_quality_score')}`",
        f"- policy_hash: `{summary.get('policy_hash')}`",
        f"- effective_guardrails_hash: `{summary.get('effective_guardrails_hash')}`",
        f"- baseline_apply_summary_path: `{summary.get('baseline_apply_summary_path')}`",
        f"- baseline_policy_hash: `{summary.get('baseline_policy_hash')}`",
        f"- baseline_effective_guardrails_hash: `{summary.get('baseline_effective_guardrails_hash')}`",
        f"- strict_guardrail_drift: `{summary.get('strict_guardrail_drift')}`",
        f"- guardrail_drift_detected: `{summary.get('guardrail_drift_detected')}`",
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
    lines.extend(["", "## Human Hints", ""])
    human_hints = summary.get("human_hints", [])
    if isinstance(human_hints, list) and human_hints:
        lines.extend([f"- {h}" for h in human_hints])
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


def _human_hints_from_reasons(reasons: list[str]) -> list[str]:
    hints: list[str] = []
    for reason in reasons:
        if reason == "ranking_explanation_required":
            hints.append(
                "Provide decision_explanations.best_vs_others with winner_profile/challenger_profile/score_margin."
            )
        elif reason == "top_score_margin_missing_when_required":
            hints.append("Ensure compare summary includes top_score_margin when min margin guard is enabled.")
        elif reason == "top_score_margin_below_required":
            hints.append("Top score margin is below required threshold; keep current profile or route to human review.")
        elif reason == "explanation_quality_missing_when_required":
            hints.append("Ensure compare summary includes explanation_quality.score when quality guard is enabled.")
        elif reason == "explanation_quality_below_required":
            hints.append("Explanation quality score is below required threshold; improve explanation quality before apply.")
        elif reason == "needs_review_ticket_required":
            hints.append("Provide a review_ticket_id to proceed with NEEDS_REVIEW apply action.")
        elif reason == "best_profile_missing":
            hints.append("Set best_profile in compare summary before applying promotion.")
        elif reason == "best_decision_invalid":
            hints.append("Set best_decision to PASS, NEEDS_REVIEW, or FAIL in compare summary.")
        elif reason == "compare_status_fail":
            hints.append("Compare status is FAIL; resolve compare issues before apply.")
        elif reason == "guardrail_policy_hash_drift":
            hints.append("Policy hash drift detected versus baseline apply summary; confirm policy change before promote.")
        elif reason == "guardrail_effective_guardrails_hash_drift":
            hints.append("Effective guardrails drift detected versus baseline; review threshold/flag changes before promote.")
    return hints


def _evaluate(
    compare_payload: dict,
    review_ticket_id: str | None,
    *,
    require_ranking_explanation: bool,
    require_min_top_score_margin: int | None,
    require_min_explanation_quality: int | None,
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
        if isinstance(require_min_explanation_quality, int):
            quality_score = compare_payload.get("explanation_quality", {}).get("score")
            if not isinstance(quality_score, int):
                reasons.append("explanation_quality_missing_when_required")
            elif quality_score < require_min_explanation_quality:
                reasons.append("explanation_quality_below_required")
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
        "--policy-profile",
        default="default",
        help="Promote-apply policy profile name in policies/promote_apply (default: default)",
    )
    parser.add_argument(
        "--policy-path",
        default=None,
        help="Explicit promote-apply policy path (overrides --policy-profile)",
    )
    parser.add_argument(
        "--require-ranking-explanation",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="When enabled, PASS compare summaries must include decision_explanations.best_vs_others",
    )
    parser.add_argument(
        "--require-min-top-score-margin",
        type=int,
        default=None,
        help="CLI override: PASS compare summaries must include top_score_margin >= this value",
    )
    parser.add_argument(
        "--require-min-explanation-quality",
        type=int,
        default=None,
        help="CLI override: PASS compare summaries must include explanation_quality.score >= this value",
    )
    parser.add_argument(
        "--baseline-apply-summary",
        default=None,
        help="Optional previous promote-apply summary JSON used to detect guardrail drift",
    )
    parser.add_argument(
        "--strict-guardrail-drift",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When enabled, guardrail drift versus baseline apply summary is FAIL (default is NEEDS_REVIEW)",
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
    policy_path = _resolve_promote_apply_policy_path(args.policy_path, args.policy_profile)
    policy_payload = _load_json(policy_path)
    effective = _resolve_effective_guardrails(args, policy_payload)
    policy_hash = _stable_hash(policy_payload)
    effective_guardrails_hash = _stable_hash(
        {
            "require_ranking_explanation": effective["require_ranking_explanation"],
            "require_min_top_score_margin": effective["require_min_top_score_margin"],
            "require_min_explanation_quality": effective["require_min_explanation_quality"],
        }
    )
    evaluated = _evaluate(
        compare_payload,
        args.review_ticket_id,
        require_ranking_explanation=bool(effective["require_ranking_explanation"]),
        require_min_top_score_margin=effective["require_min_top_score_margin"],
        require_min_explanation_quality=effective["require_min_explanation_quality"],
    )
    drift = _detect_guardrail_drift(
        baseline_summary_path=args.baseline_apply_summary,
        current_policy_hash=policy_hash,
        current_effective_hash=effective_guardrails_hash,
    )
    if drift["drift_reasons"]:
        existing_reasons = [str(r) for r in evaluated.get("reasons", [])]
        merged_reasons: list[str] = []
        for reason in [*existing_reasons, *drift["drift_reasons"]]:
            if reason not in merged_reasons:
                merged_reasons.append(reason)
        evaluated["reasons"] = merged_reasons
        if args.strict_guardrail_drift:
            evaluated["final_status"] = "FAIL"
            evaluated["apply_action"] = "block"
        elif evaluated.get("final_status") == "PASS":
            evaluated["final_status"] = "NEEDS_REVIEW"
            evaluated["apply_action"] = "hold_for_review"
    recorded_at = datetime.now(timezone.utc).isoformat()

    summary = {
        **evaluated,
        "actor": args.actor,
        "review_ticket_id": args.review_ticket_id,
        "policy_profile": args.policy_profile,
        "policy_version": policy_payload.get("version"),
        "policy_path": policy_path,
        "policy_hash": policy_hash,
        "effective_guardrails_hash": effective_guardrails_hash,
        "require_ranking_explanation": effective["require_ranking_explanation"],
        "source_require_ranking_explanation": effective["source_require_ranking_explanation"],
        "require_min_top_score_margin": effective["require_min_top_score_margin"],
        "source_require_min_top_score_margin": effective["source_require_min_top_score_margin"],
        "require_min_explanation_quality": effective["require_min_explanation_quality"],
        "source_require_min_explanation_quality": effective["source_require_min_explanation_quality"],
        "compare_summary_path": args.compare_summary,
        "constraint_reason": compare_payload.get("constraint_reason"),
        "top_score_margin": compare_payload.get("top_score_margin"),
        "min_top_score_margin": compare_payload.get("min_top_score_margin"),
        "best_total_score": compare_payload.get("best_total_score"),
        "best_reason": compare_payload.get("best_reason"),
        "ranking_selection_priority": compare_payload.get("decision_explanations", {}).get("selection_priority"),
        "ranking_best_vs_others": compare_payload.get("decision_explanations", {}).get("best_vs_others"),
        "explanation_quality_score": compare_payload.get("explanation_quality", {}).get("score"),
        "baseline_apply_summary_path": drift["baseline_apply_summary_path"],
        "baseline_policy_hash": drift["baseline_policy_hash"],
        "baseline_effective_guardrails_hash": drift["baseline_effective_guardrails_hash"],
        "strict_guardrail_drift": bool(args.strict_guardrail_drift),
        "guardrail_drift_detected": bool(drift["drift_reasons"]),
        "human_hints": _human_hints_from_reasons(evaluated.get("reasons", [])),
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
        "human_hints": summary.get("human_hints", []),
        "compare_summary_path": args.compare_summary,
        "compare_status": summary.get("compare_status"),
        "best_profile": summary.get("best_profile"),
        "best_decision": summary.get("best_decision"),
        "recommended_profile": summary.get("recommended_profile"),
        "review_ticket_id": summary.get("review_ticket_id"),
        "policy_profile": summary.get("policy_profile"),
        "policy_version": summary.get("policy_version"),
        "policy_path": summary.get("policy_path"),
        "policy_hash": summary.get("policy_hash"),
        "effective_guardrails_hash": summary.get("effective_guardrails_hash"),
        "require_ranking_explanation": summary.get("require_ranking_explanation"),
        "source_require_ranking_explanation": summary.get("source_require_ranking_explanation"),
        "require_min_top_score_margin": summary.get("require_min_top_score_margin"),
        "source_require_min_top_score_margin": summary.get("source_require_min_top_score_margin"),
        "require_min_explanation_quality": summary.get("require_min_explanation_quality"),
        "source_require_min_explanation_quality": summary.get("source_require_min_explanation_quality"),
        "baseline_apply_summary_path": summary.get("baseline_apply_summary_path"),
        "baseline_policy_hash": summary.get("baseline_policy_hash"),
        "baseline_effective_guardrails_hash": summary.get("baseline_effective_guardrails_hash"),
        "strict_guardrail_drift": summary.get("strict_guardrail_drift"),
        "guardrail_drift_detected": summary.get("guardrail_drift_detected"),
        "constraint_reason": summary.get("constraint_reason"),
        "top_score_margin": summary.get("top_score_margin"),
        "min_top_score_margin": summary.get("min_top_score_margin"),
        "explanation_quality_score": summary.get("explanation_quality_score"),
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
