from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .governance_promote_compare_validate import validate_compare_summary

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
    pairwise_net_margin_from_cli = args.require_min_pairwise_net_margin is not None
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
    min_pairwise_net_margin = (
        args.require_min_pairwise_net_margin
        if pairwise_net_margin_from_cli
        else policy_payload.get("require_min_pairwise_net_margin")
    )
    min_quality = (
        args.require_min_explanation_quality
        if quality_from_cli
        else policy_payload.get("require_min_explanation_quality")
    )

    if min_margin is not None and not isinstance(min_margin, int):
        raise ValueError("effective require_min_top_score_margin must be int or null")
    if min_pairwise_net_margin is not None and not isinstance(min_pairwise_net_margin, int):
        raise ValueError("effective require_min_pairwise_net_margin must be int or null")
    if min_quality is not None and not isinstance(min_quality, int):
        raise ValueError("effective require_min_explanation_quality must be int or null")

    return {
        "require_ranking_explanation": require_ranking,
        "require_min_top_score_margin": min_margin,
        "require_min_pairwise_net_margin": min_pairwise_net_margin,
        "require_min_explanation_quality": min_quality,
        "source_require_ranking_explanation": "cli" if rank_from_cli else "policy_profile",
        "source_require_min_top_score_margin": "cli" if margin_from_cli else "policy_profile",
        "source_require_min_pairwise_net_margin": "cli" if pairwise_net_margin_from_cli else "policy_profile",
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
        "require_min_pairwise_net_margin": summary.get("require_min_pairwise_net_margin"),
        "require_min_explanation_quality": summary.get("require_min_explanation_quality"),
    }
    if not isinstance(baseline_effective["require_ranking_explanation"], bool):
        return None
    if baseline_effective["require_min_top_score_margin"] is not None and not isinstance(
        baseline_effective["require_min_top_score_margin"], int
    ):
        return None
    if baseline_effective["require_min_pairwise_net_margin"] is not None and not isinstance(
        baseline_effective["require_min_pairwise_net_margin"], int
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
        f"- require_min_pairwise_net_margin: `{summary.get('require_min_pairwise_net_margin')}`",
        f"- source_require_min_pairwise_net_margin: `{summary.get('source_require_min_pairwise_net_margin')}`",
        f"- require_min_explanation_quality: `{summary.get('require_min_explanation_quality')}`",
        f"- source_require_min_explanation_quality: `{summary.get('source_require_min_explanation_quality')}`",
        f"- explanation_quality_score: `{summary.get('explanation_quality_score')}`",
        f"- explanation_completeness: `{summary.get('explanation_completeness')}`",
        f"- policy_hash: `{summary.get('policy_hash')}`",
        f"- effective_guardrails_hash: `{summary.get('effective_guardrails_hash')}`",
        f"- baseline_apply_summary_path: `{summary.get('baseline_apply_summary_path')}`",
        f"- baseline_policy_hash: `{summary.get('baseline_policy_hash')}`",
        f"- baseline_effective_guardrails_hash: `{summary.get('baseline_effective_guardrails_hash')}`",
        f"- strict_guardrail_drift: `{summary.get('strict_guardrail_drift')}`",
        f"- guardrail_drift_detected: `{summary.get('guardrail_drift_detected')}`",
        f"- require_ranking_explanation_structure: `{summary.get('require_ranking_explanation_structure')}`",
        f"- strict_ranking_explanation_structure: `{summary.get('strict_ranking_explanation_structure')}`",
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
    lines.extend(["", "## Ranking Structure Errors", ""])
    structure_errors = summary.get("ranking_explanation_structure_errors", [])
    if isinstance(structure_errors, list) and structure_errors:
        lines.extend([f"- `{err}`" for err in structure_errors])
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
    lines.extend(["", "## Ranking Explanation Ranked Reasons", ""])
    ranked = summary.get("ranking_decision_explanation_ranked", [])
    if isinstance(ranked, list) and ranked:
        for row in ranked:
            lines.append(
                f"- reason=`{row.get('reason')}` value=`{row.get('value')}` weight=`{row.get('weight')}` note=`{row.get('note')}`"
            )
    else:
        lines.append("- `none`")
    lines.extend(["", "## Ranking Explanation Details", ""])
    lines.append(f"- top_driver: `{summary.get('ranking_explanation_top_driver')}`")
    lines.append(f"- numeric_reason_count: `{summary.get('ranking_explanation_numeric_reason_count')}`")
    details = summary.get("ranking_decision_explanation_details", [])
    if isinstance(details, list) and details:
        for row in details:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- rank=`{row.get('rank')}` reason=`{row.get('reason')}` impact_score=`{row.get('impact_score')}` "
                f"impact_share_pct=`{row.get('impact_share_pct')}` weight=`{row.get('weight')}` value=`{row.get('value')}`"
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


def _ranking_explanation_structure_errors(best_vs_others: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(best_vs_others, list) or not best_vs_others:
        return ["best_vs_others_missing_or_empty"]
    for idx, row in enumerate(best_vs_others):
        prefix = f"row[{idx}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix}_not_object")
            continue
        for key in ("winner_profile", "challenger_profile"):
            value = row.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}_{key}_invalid")
        if not isinstance(row.get("score_margin"), int):
            errors.append(f"{prefix}_score_margin_invalid")
        if not isinstance(row.get("tie_on_total_score"), bool):
            errors.append(f"{prefix}_tie_on_total_score_invalid")
        advantages = row.get("winner_advantages")
        if not isinstance(advantages, list) or not advantages or not all(isinstance(v, str) for v in advantages):
            errors.append(f"{prefix}_winner_advantages_invalid")
        delta = row.get("score_breakdown_delta")
        if not isinstance(delta, dict):
            errors.append(f"{prefix}_score_breakdown_delta_invalid")
        else:
            for key in (
                "decision_component",
                "exit_component",
                "reasons_component",
                "recommended_component",
                "total_score",
            ):
                if not isinstance(delta.get(key), int):
                    errors.append(f"{prefix}_score_breakdown_delta_{key}_invalid")
        ranked = row.get("ranked_advantages")
        if not isinstance(ranked, list) or not ranked:
            errors.append(f"{prefix}_ranked_advantages_invalid")
        else:
            for sub_idx, item in enumerate(ranked):
                if not isinstance(item, dict):
                    errors.append(f"{prefix}_ranked_advantages[{sub_idx}]_not_object")
                    continue
                if not isinstance(item.get("component"), str) or not item.get("component"):
                    errors.append(f"{prefix}_ranked_advantages[{sub_idx}]_component_invalid")
                if not isinstance(item.get("delta"), int):
                    errors.append(f"{prefix}_ranked_advantages[{sub_idx}]_delta_invalid")
    return errors


def _ranking_explanation_meta_errors(compare_payload: dict) -> list[str]:
    errors: list[str] = []
    ranked = compare_payload.get("decision_explanation_ranked")
    if not isinstance(ranked, list) or not ranked:
        errors.append("decision_explanation_ranked_missing_or_empty")
    else:
        for idx, row in enumerate(ranked):
            prefix = f"decision_explanation_ranked[{idx}]"
            if not isinstance(row, dict):
                errors.append(f"{prefix}_not_object")
                continue
            if not isinstance(row.get("reason"), str) or not row.get("reason"):
                errors.append(f"{prefix}_reason_invalid")
            if not isinstance(row.get("weight"), int):
                errors.append(f"{prefix}_weight_invalid")
            if "value" not in row:
                errors.append(f"{prefix}_value_missing")
            note = row.get("note")
            if note is not None and not isinstance(note, str):
                errors.append(f"{prefix}_note_invalid")
    completeness = compare_payload.get("explanation_completeness")
    if not isinstance(completeness, int):
        errors.append("explanation_completeness_invalid")
    elif completeness < 0 or completeness > 100:
        errors.append("explanation_completeness_out_of_range")
    ranking_details = compare_payload.get("decision_explanation_ranking_details")
    if not isinstance(ranking_details, dict):
        errors.append("decision_explanation_ranking_details_invalid")
    else:
        top_driver = ranking_details.get("top_driver")
        if not isinstance(top_driver, str) or not top_driver:
            errors.append("decision_explanation_ranking_details_top_driver_invalid")
        numeric_reason_count = ranking_details.get("numeric_reason_count")
        if not isinstance(numeric_reason_count, int) or numeric_reason_count < 0:
            errors.append("decision_explanation_ranking_details_numeric_reason_count_invalid")
        drivers = ranking_details.get("drivers")
        if not isinstance(drivers, list) or not drivers:
            errors.append("decision_explanation_ranking_details_drivers_missing_or_empty")
        else:
            for idx, row in enumerate(drivers):
                prefix = f"decision_explanation_ranking_details.drivers[{idx}]"
                if not isinstance(row, dict):
                    errors.append(f"{prefix}_not_object")
                    continue
                if not isinstance(row.get("rank"), int):
                    errors.append(f"{prefix}_rank_invalid")
                if not isinstance(row.get("reason"), str) or not row.get("reason"):
                    errors.append(f"{prefix}_reason_invalid")
                if not isinstance(row.get("weight"), int):
                    errors.append(f"{prefix}_weight_invalid")
                if not isinstance(row.get("impact_score"), int):
                    errors.append(f"{prefix}_impact_score_invalid")
                if not isinstance(row.get("impact_share_pct"), (int, float)):
                    errors.append(f"{prefix}_impact_share_pct_invalid")
                if "value" not in row:
                    errors.append(f"{prefix}_value_missing")
    return errors


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
        elif reason == "pairwise_net_margin_missing_when_required":
            hints.append("Ensure compare summary includes decision_explanation_leaderboard[0].pairwise_net_margin.")
        elif reason == "pairwise_net_margin_below_required":
            hints.append("Pairwise net margin is below required threshold; keep current profile or route to human review.")
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
        elif reason == "ranking_explanation_structure_invalid":
            hints.append("Ranking explanation structure is incomplete; include score delta and ranked advantages for each pair.")
    return hints


def _evaluate(
    compare_payload: dict,
    review_ticket_id: str | None,
    *,
    require_ranking_explanation: bool,
    require_min_top_score_margin: int | None,
    require_min_pairwise_net_margin: int | None,
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
        if isinstance(require_min_pairwise_net_margin, int):
            leaderboard = compare_payload.get("decision_explanation_leaderboard")
            pairwise_net_margin = None
            if isinstance(leaderboard, list) and leaderboard and isinstance(leaderboard[0], dict):
                pairwise_net_margin = leaderboard[0].get("pairwise_net_margin")
            if not isinstance(pairwise_net_margin, int):
                reasons.append("pairwise_net_margin_missing_when_required")
            elif pairwise_net_margin < require_min_pairwise_net_margin:
                reasons.append("pairwise_net_margin_below_required")
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
        "--require-min-pairwise-net-margin",
        type=int,
        default=None,
        help="CLI override: PASS compare summaries must include decision_explanation_leaderboard[0].pairwise_net_margin >= this value",
    )
    parser.add_argument(
        "--require-min-explanation-quality",
        type=int,
        default=None,
        help="CLI override: PASS compare summaries must include explanation_quality.score >= this value",
    )
    parser.add_argument(
        "--require-ranking-explanation-structure",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When enabled, PASS compare summaries must include full ranking explanation structure",
    )
    parser.add_argument(
        "--strict-ranking-explanation-structure",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When enabled with --require-ranking-explanation-structure, invalid structure becomes FAIL (default is NEEDS_REVIEW)",
    )
    parser.add_argument(
        "--validate-compare-summary",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Validate compare summary structure before apply decision",
    )
    parser.add_argument(
        "--validate-compare-apply-ready",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When validating compare summary, enforce full apply-ready structure checks",
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
    if bool(args.validate_compare_summary):
        validation_errors = validate_compare_summary(
            compare_payload,
            require_apply_ready=bool(args.validate_compare_apply_ready),
        )
        if validation_errors:
            hint = "Fix compare summary fields before governance_promote_apply."
            payload = {
                "final_status": "FAIL",
                "apply_action": "block",
                "reasons": ["compare_summary_invalid_structure"],
                "compare_summary_validation_errors": validation_errors,
                "human_hints": [hint],
                "compare_summary_path": args.compare_summary,
                "actor": args.actor,
                "review_ticket_id": args.review_ticket_id,
                "policy_profile": args.policy_profile,
                "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                "audit_path": args.audit,
            }
            _write_json(args.out, payload)
            _write_markdown(args.report or _default_md_path(args.out), payload)
            _append_jsonl(
                args.audit,
                {
                    "recorded_at_utc": payload["recorded_at_utc"],
                    "actor": args.actor,
                    "final_status": payload["final_status"],
                    "apply_action": payload["apply_action"],
                    "reasons": payload["reasons"],
                    "human_hints": payload["human_hints"],
                    "compare_summary_path": args.compare_summary,
                    "compare_summary_validation_errors": validation_errors,
                    "policy_profile": args.policy_profile,
                },
            )
            print(
                json.dumps(
                    {
                        "final_status": payload["final_status"],
                        "apply_action": payload["apply_action"],
                        "best_profile": None,
                    }
                )
            )
            sys.exit(1)
    policy_path = _resolve_promote_apply_policy_path(args.policy_path, args.policy_profile)
    policy_payload = _load_json(policy_path)
    effective = _resolve_effective_guardrails(args, policy_payload)
    policy_hash = _stable_hash(policy_payload)
    effective_guardrails_hash = _stable_hash(
        {
            "require_ranking_explanation": effective["require_ranking_explanation"],
            "require_min_top_score_margin": effective["require_min_top_score_margin"],
            "require_min_pairwise_net_margin": effective["require_min_pairwise_net_margin"],
            "require_min_explanation_quality": effective["require_min_explanation_quality"],
        }
    )
    evaluated = _evaluate(
        compare_payload,
        args.review_ticket_id,
        require_ranking_explanation=bool(effective["require_ranking_explanation"]),
        require_min_top_score_margin=effective["require_min_top_score_margin"],
        require_min_pairwise_net_margin=effective["require_min_pairwise_net_margin"],
        require_min_explanation_quality=effective["require_min_explanation_quality"],
    )
    structure_errors: list[str] = []
    if bool(args.require_ranking_explanation_structure) and str(compare_payload.get("status", "")).upper() == "PASS":
        structure_errors = _ranking_explanation_structure_errors(
            compare_payload.get("decision_explanations", {}).get("best_vs_others")
        )
        structure_errors.extend(_ranking_explanation_meta_errors(compare_payload))
        if structure_errors:
            existing_reasons = [str(r) for r in evaluated.get("reasons", [])]
            if "ranking_explanation_structure_invalid" not in existing_reasons:
                existing_reasons.append("ranking_explanation_structure_invalid")
            evaluated["reasons"] = existing_reasons
            if bool(args.strict_ranking_explanation_structure):
                evaluated["final_status"] = "FAIL"
                evaluated["apply_action"] = "block"
            elif evaluated.get("final_status") == "PASS":
                evaluated["final_status"] = "NEEDS_REVIEW"
                evaluated["apply_action"] = "hold_for_review"
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
        "require_min_pairwise_net_margin": effective["require_min_pairwise_net_margin"],
        "source_require_min_pairwise_net_margin": effective["source_require_min_pairwise_net_margin"],
        "require_min_explanation_quality": effective["require_min_explanation_quality"],
        "source_require_min_explanation_quality": effective["source_require_min_explanation_quality"],
        "compare_summary_path": args.compare_summary,
        "constraint_reason": compare_payload.get("constraint_reason"),
        "top_score_margin": compare_payload.get("top_score_margin"),
        "pairwise_net_margin": (
            compare_payload.get("decision_explanation_leaderboard", [{}])[0].get("pairwise_net_margin")
            if isinstance(compare_payload.get("decision_explanation_leaderboard"), list)
            and compare_payload.get("decision_explanation_leaderboard")
            and isinstance(compare_payload.get("decision_explanation_leaderboard")[0], dict)
            else None
        ),
        "min_top_score_margin": compare_payload.get("min_top_score_margin"),
        "best_total_score": compare_payload.get("best_total_score"),
        "best_reason": compare_payload.get("best_reason"),
        "ranking_selection_priority": compare_payload.get("decision_explanations", {}).get("selection_priority"),
        "ranking_best_vs_others": compare_payload.get("decision_explanations", {}).get("best_vs_others"),
        "ranking_decision_explanation_ranked": compare_payload.get("decision_explanation_ranked"),
        "ranking_explanation_top_driver": compare_payload.get("decision_explanation_ranking_details", {}).get(
            "top_driver"
        ),
        "ranking_explanation_numeric_reason_count": compare_payload.get(
            "decision_explanation_ranking_details", {}
        ).get("numeric_reason_count"),
        "ranking_decision_explanation_details": compare_payload.get("decision_explanation_ranking_details", {}).get(
            "drivers"
        ),
        "explanation_quality_score": compare_payload.get("explanation_quality", {}).get("score"),
        "explanation_completeness": compare_payload.get("explanation_completeness"),
        "baseline_apply_summary_path": drift["baseline_apply_summary_path"],
        "baseline_policy_hash": drift["baseline_policy_hash"],
        "baseline_effective_guardrails_hash": drift["baseline_effective_guardrails_hash"],
        "strict_guardrail_drift": bool(args.strict_guardrail_drift),
        "guardrail_drift_detected": bool(drift["drift_reasons"]),
        "require_ranking_explanation_structure": bool(args.require_ranking_explanation_structure),
        "strict_ranking_explanation_structure": bool(args.strict_ranking_explanation_structure),
        "ranking_explanation_structure_errors": structure_errors,
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
        "require_min_pairwise_net_margin": summary.get("require_min_pairwise_net_margin"),
        "source_require_min_pairwise_net_margin": summary.get("source_require_min_pairwise_net_margin"),
        "require_min_explanation_quality": summary.get("require_min_explanation_quality"),
        "source_require_min_explanation_quality": summary.get("source_require_min_explanation_quality"),
        "baseline_apply_summary_path": summary.get("baseline_apply_summary_path"),
        "baseline_policy_hash": summary.get("baseline_policy_hash"),
        "baseline_effective_guardrails_hash": summary.get("baseline_effective_guardrails_hash"),
        "strict_guardrail_drift": summary.get("strict_guardrail_drift"),
        "guardrail_drift_detected": summary.get("guardrail_drift_detected"),
        "require_ranking_explanation_structure": summary.get("require_ranking_explanation_structure"),
        "strict_ranking_explanation_structure": summary.get("strict_ranking_explanation_structure"),
        "ranking_explanation_structure_errors": summary.get("ranking_explanation_structure_errors"),
        "constraint_reason": summary.get("constraint_reason"),
        "top_score_margin": summary.get("top_score_margin"),
        "min_top_score_margin": summary.get("min_top_score_margin"),
        "explanation_quality_score": summary.get("explanation_quality_score"),
        "ranking_selection_priority": summary.get("ranking_selection_priority"),
        "ranking_best_vs_others": summary.get("ranking_best_vs_others"),
        "ranking_decision_explanation_ranked": summary.get("ranking_decision_explanation_ranked"),
        "ranking_explanation_top_driver": summary.get("ranking_explanation_top_driver"),
        "ranking_explanation_numeric_reason_count": summary.get("ranking_explanation_numeric_reason_count"),
        "ranking_decision_explanation_details": summary.get("ranking_decision_explanation_details"),
        "explanation_completeness": summary.get("explanation_completeness"),
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
