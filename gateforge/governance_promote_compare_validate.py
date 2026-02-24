from __future__ import annotations

import argparse
import json
from pathlib import Path


def _is_non_empty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_compare_summary(payload: dict, *, require_apply_ready: bool = True) -> list[str]:
    errors: list[str] = []
    status = str(payload.get("status") or "").upper()
    if status not in {"PASS", "NEEDS_REVIEW", "FAIL"}:
        errors.append("status_invalid")
        return errors

    if status != "PASS":
        return errors

    if not _is_non_empty_str(payload.get("best_profile")):
        errors.append("best_profile_invalid")
    if str(payload.get("best_decision") or "").upper() not in {"PASS", "NEEDS_REVIEW", "FAIL"}:
        errors.append("best_decision_invalid")
    if not isinstance(payload.get("top_score_margin"), int):
        errors.append("top_score_margin_invalid")

    explanations = payload.get("decision_explanations")
    if not isinstance(explanations, dict):
        return errors + ["decision_explanations_invalid"]

    selection_priority = explanations.get("selection_priority")
    if (
        not isinstance(selection_priority, list)
        or not selection_priority
        or not all(_is_non_empty_str(v) for v in selection_priority)
    ):
        errors.append("selection_priority_invalid")

    best_vs_others = explanations.get("best_vs_others")
    if not isinstance(best_vs_others, list) or not best_vs_others:
        return errors + ["best_vs_others_missing_or_empty"]

    for idx, row in enumerate(best_vs_others):
        if not isinstance(row, dict):
            errors.append(f"best_vs_others[{idx}]_not_object")
            continue
        if not _is_non_empty_str(row.get("winner_profile")):
            errors.append(f"best_vs_others[{idx}]_winner_profile_invalid")
        if not _is_non_empty_str(row.get("challenger_profile")):
            errors.append(f"best_vs_others[{idx}]_challenger_profile_invalid")
        if not isinstance(row.get("score_margin"), int):
            errors.append(f"best_vs_others[{idx}]_score_margin_invalid")
        if not isinstance(row.get("tie_on_total_score"), bool):
            errors.append(f"best_vs_others[{idx}]_tie_on_total_score_invalid")
        advantages = row.get("winner_advantages")
        if not isinstance(advantages, list) or not advantages or not all(_is_non_empty_str(v) for v in advantages):
            errors.append(f"best_vs_others[{idx}]_winner_advantages_invalid")

        if not require_apply_ready:
            continue

        delta = row.get("score_breakdown_delta")
        if not isinstance(delta, dict):
            errors.append(f"best_vs_others[{idx}]_score_breakdown_delta_invalid")
        else:
            for key in (
                "decision_component",
                "exit_component",
                "reasons_component",
                "recommended_component",
                "total_score",
            ):
                if not isinstance(delta.get(key), int):
                    errors.append(f"best_vs_others[{idx}]_score_breakdown_delta_{key}_invalid")

        ranked_adv = row.get("ranked_advantages")
        if not isinstance(ranked_adv, list) or not ranked_adv:
            errors.append(f"best_vs_others[{idx}]_ranked_advantages_invalid")
        else:
            for sub_idx, item in enumerate(ranked_adv):
                if not isinstance(item, dict):
                    errors.append(f"best_vs_others[{idx}]_ranked_advantages[{sub_idx}]_not_object")
                    continue
                if not _is_non_empty_str(item.get("component")):
                    errors.append(f"best_vs_others[{idx}]_ranked_advantages[{sub_idx}]_component_invalid")
                if not isinstance(item.get("delta"), int):
                    errors.append(f"best_vs_others[{idx}]_ranked_advantages[{sub_idx}]_delta_invalid")

    if not require_apply_ready:
        return errors

    leaderboard = payload.get("decision_explanation_leaderboard")
    if not isinstance(leaderboard, list) or not leaderboard:
        errors.append("decision_explanation_leaderboard_missing_or_empty")
    elif not isinstance(leaderboard[0], dict) or not isinstance(leaderboard[0].get("pairwise_net_margin"), int):
        errors.append("decision_explanation_leaderboard_pairwise_net_margin_invalid")

    ranked = payload.get("decision_explanation_ranked")
    if not isinstance(ranked, list) or not ranked:
        errors.append("decision_explanation_ranked_missing_or_empty")
    else:
        for idx, item in enumerate(ranked):
            if not isinstance(item, dict):
                errors.append(f"decision_explanation_ranked[{idx}]_not_object")
                continue
            if not _is_non_empty_str(item.get("reason")):
                errors.append(f"decision_explanation_ranked[{idx}]_reason_invalid")
            if not isinstance(item.get("weight"), int):
                errors.append(f"decision_explanation_ranked[{idx}]_weight_invalid")
            if "value" not in item:
                errors.append(f"decision_explanation_ranked[{idx}]_value_missing")

    details = payload.get("decision_explanation_ranking_details")
    if not isinstance(details, dict):
        errors.append("decision_explanation_ranking_details_invalid")
    else:
        if not _is_non_empty_str(details.get("top_driver")):
            errors.append("decision_explanation_ranking_details_top_driver_invalid")
        if not isinstance(details.get("numeric_reason_count"), int) or int(details.get("numeric_reason_count")) < 0:
            errors.append("decision_explanation_ranking_details_numeric_reason_count_invalid")
        drivers = details.get("drivers")
        if not isinstance(drivers, list) or not drivers:
            errors.append("decision_explanation_ranking_details_drivers_missing_or_empty")
        else:
            for idx, item in enumerate(drivers):
                if not isinstance(item, dict):
                    errors.append(f"decision_explanation_ranking_details.drivers[{idx}]_not_object")
                    continue
                if not isinstance(item.get("rank"), int):
                    errors.append(f"decision_explanation_ranking_details.drivers[{idx}]_rank_invalid")
                if not _is_non_empty_str(item.get("reason")):
                    errors.append(f"decision_explanation_ranking_details.drivers[{idx}]_reason_invalid")
                if not isinstance(item.get("weight"), int):
                    errors.append(f"decision_explanation_ranking_details.drivers[{idx}]_weight_invalid")
                if not isinstance(item.get("impact_score"), int):
                    errors.append(f"decision_explanation_ranking_details.drivers[{idx}]_impact_score_invalid")
                if not isinstance(item.get("impact_share_pct"), (int, float)):
                    errors.append(f"decision_explanation_ranking_details.drivers[{idx}]_impact_share_pct_invalid")
                if "value" not in item:
                    errors.append(f"decision_explanation_ranking_details.drivers[{idx}]_value_missing")

    completeness = payload.get("explanation_completeness")
    if not isinstance(completeness, int) or completeness < 0 or completeness > 100:
        errors.append("explanation_completeness_invalid")

    quality = payload.get("explanation_quality")
    if not isinstance(quality, dict) or not isinstance(quality.get("score"), int):
        errors.append("explanation_quality_score_invalid")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate governance_promote_compare summary JSON")
    parser.add_argument("--in", dest="in_path", required=True, help="Compare summary JSON path")
    parser.add_argument(
        "--require-apply-ready",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Validate strict fields required by governance_promote_apply guardrails",
    )
    args = parser.parse_args()

    payload = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    errors = validate_compare_summary(payload, require_apply_ready=bool(args.require_apply_ready))
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors, "path": args.in_path}))
        raise SystemExit(1)
    print(json.dumps({"status": "PASS", "path": args.in_path}))


if __name__ == "__main__":
    main()
