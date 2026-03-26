from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "agent_modelica_repair_quality_score_v1"

CORRECTNESS_WEIGHT = 0.5
EFFICIENCY_WEIGHT = 0.2
WASTED_ROUNDS_WEIGHT = 0.1
LLM_BUDGET_WEIGHT = 0.1
RULE_ONLY_BONUS_WEIGHT = 0.1
DEFAULT_ROUND_BUDGET = 5


def _to_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _hard_success(run_result: dict) -> bool:
    return bool(
        bool(run_result.get("check_model_pass"))
        and bool(run_result.get("simulate_pass"))
        and bool(run_result.get("physics_contract_pass"))
        and bool(run_result.get("regression_pass"))
    )


def _attempts(run_result: dict) -> list[dict]:
    attempts = run_result.get("attempts") if isinstance(run_result.get("attempts"), list) else []
    return [row for row in attempts if isinstance(row, dict)]


def _rounds_used(run_result: dict) -> int:
    attempts = _attempts(run_result)
    for attempt in attempts:
        if bool(attempt.get("check_model_pass")) and bool(attempt.get("simulate_pass")):
            return max(1, _to_int(attempt.get("round"), 1))
    return max(1, len(attempts))


def _wasted_rounds(run_result: dict) -> int:
    wasted = 0
    previous = ""
    for attempt in _attempts(run_result):
        current = str(attempt.get("observed_failure_type") or "").strip().lower()
        if previous and current and current == previous:
            wasted += 1
        previous = current
    return wasted


def _llm_request_count(run_result: dict) -> int:
    attempts = _attempts(run_result)
    attempt_delta_total = sum(_to_int(attempt.get("llm_request_count_delta"), 0) for attempt in attempts)
    return max(_to_int(run_result.get("live_request_count"), 0), int(attempt_delta_total))


def compute_repair_quality_breakdown(run_result: dict) -> dict:
    hard_success = _hard_success(run_result)
    rounds_used = _rounds_used(run_result)
    wasted_rounds = _wasted_rounds(run_result)
    llm_request_count = _llm_request_count(run_result)

    correctness_score = 1.0 if hard_success else 0.0
    efficiency_score = max(0.0, 1.0 - ((min(rounds_used, DEFAULT_ROUND_BUDGET) - 1) / max(1, DEFAULT_ROUND_BUDGET - 1)))
    wasted_rounds_score = 1.0 if rounds_used <= 1 else max(0.0, 1.0 - (float(wasted_rounds) / float(max(1, rounds_used - 1))))
    llm_budget_score = max(0.0, 1.0 - (float(min(llm_request_count, max(1, rounds_used))) / float(max(1, rounds_used))))
    rule_only_bonus_score = 1.0 if hard_success and llm_request_count == 0 else 0.0

    if hard_success:
        repair_quality_score = round(
            (CORRECTNESS_WEIGHT * correctness_score)
            + (EFFICIENCY_WEIGHT * efficiency_score)
            + (WASTED_ROUNDS_WEIGHT * wasted_rounds_score)
            + (LLM_BUDGET_WEIGHT * llm_budget_score)
            + (RULE_ONLY_BONUS_WEIGHT * rule_only_bonus_score),
            4,
        )
    else:
        repair_quality_score = 0.0

    return {
        "schema_version": SCHEMA_VERSION,
        "repair_quality_score": repair_quality_score,
        "components": {
            "correctness_score": correctness_score,
            "efficiency_score": round(efficiency_score, 4),
            "wasted_rounds_score": round(wasted_rounds_score, 4),
            "llm_budget_score": round(llm_budget_score, 4),
            "rule_only_bonus_score": rule_only_bonus_score,
        },
        "weights": {
            "correctness": CORRECTNESS_WEIGHT,
            "efficiency": EFFICIENCY_WEIGHT,
            "wasted_rounds": WASTED_ROUNDS_WEIGHT,
            "llm_budget": LLM_BUDGET_WEIGHT,
            "rule_only_bonus": RULE_ONLY_BONUS_WEIGHT,
        },
        "metrics": {
            "rounds_used": rounds_used,
            "wasted_rounds": wasted_rounds,
            "llm_request_count": llm_request_count,
            "hard_success": hard_success,
        },
    }

