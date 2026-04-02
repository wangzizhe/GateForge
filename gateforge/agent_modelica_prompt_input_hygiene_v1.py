from __future__ import annotations

from .agent_modelica_context_truncation_v1 import (
    truncate_context as _truncate_context,
)


_EMPTY_CONTEXT_TRUNCATION_SUMMARY = {
    "was_truncated": False,
    "truncation_reason": "none",
    "original_line_count": 0,
    "original_byte_count": 0,
    "final_line_count": 0,
    "final_byte_count": 0,
}


def default_context_truncation_summary() -> dict:
    """Return a fresh empty truncation summary dict."""
    return dict(_EMPTY_CONTEXT_TRUNCATION_SUMMARY)


def truncate_planner_experience_context(
    context: dict,
    *,
    label: str = "planner_experience_context",
) -> tuple[dict, dict]:
    """Apply outer dual-cap truncation to planner experience prompt text."""
    raw_text = str(context.get("prompt_context_text") or "")
    truncation = _truncate_context(
        raw_text,
        label=label,
    )
    updated = dict(context)
    updated["prompt_context_text"] = truncation.text
    updated["outer_context_truncation"] = truncation.summary()
    updated["truncated"] = bool(context.get("truncated")) or bool(truncation.was_truncated)
    return updated, truncation.summary()


def _cap_string_list(values: object, *, max_items: int) -> tuple[list[str], dict]:
    items = [str(x) for x in (values or []) if str(x).strip()]
    capped = items[:max_items]
    return capped, {
        "original_count": len(items),
        "final_count": len(capped),
        "was_truncated": len(items) > len(capped),
    }


def truncate_replan_context_for_prompt(
    context: dict,
    *,
    max_items_per_list: int = 6,
) -> tuple[dict, dict]:
    """Cap prompt-relevant replan-context lists before LLM invocation."""
    updated = dict(context)
    previous_candidate_parameters, previous_parameter_summary = _cap_string_list(
        context.get("previous_candidate_parameters"),
        max_items=max_items_per_list,
    )
    previous_candidate_directions, previous_direction_summary = _cap_string_list(
        context.get("previous_candidate_value_directions"),
        max_items=max_items_per_list,
    )
    updated["previous_candidate_parameters"] = previous_candidate_parameters
    updated["previous_candidate_value_directions"] = previous_candidate_directions

    guided_search_observation = context.get("guided_search_observation")
    guided_summary: dict[str, dict] = {}
    if isinstance(guided_search_observation, dict):
        guided_updated = dict(guided_search_observation)
        for key in (
            "guided_search_bucket_sequence",
            "no_progress_buckets",
            "abandoned_branches",
            "branch_frozen_by_budget",
        ):
            capped_values, capped_summary = _cap_string_list(
                guided_search_observation.get(key),
                max_items=max_items_per_list,
            )
            guided_updated[key] = capped_values
            guided_summary[key] = capped_summary
        updated["guided_search_observation"] = guided_updated

    summary = {
        "max_items_per_list": int(max_items_per_list),
        "previous_candidate_parameters": previous_parameter_summary,
        "previous_candidate_value_directions": previous_direction_summary,
        "guided_search_observation": guided_summary,
    }
    summary["was_truncated"] = bool(
        previous_parameter_summary["was_truncated"]
        or previous_direction_summary["was_truncated"]
        or any(bool(v.get("was_truncated")) for v in guided_summary.values())
    )
    return updated, summary
