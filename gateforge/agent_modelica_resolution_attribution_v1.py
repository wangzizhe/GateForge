from __future__ import annotations

from collections import Counter

from .agent_modelica_diagnostic_ir_v0 import dominant_stage_subtype_v0


SCHEMA_VERSION = "agent_modelica_resolution_attribution_v1"


def _attempts(run_result: dict) -> list[dict]:
    attempts = run_result.get("attempts") if isinstance(run_result.get("attempts"), list) else []
    return [row for row in attempts if isinstance(row, dict)]


def _success(run_result: dict) -> bool:
    if bool(run_result.get("passed")):
        return True
    hard_checks = run_result.get("hard_checks") if isinstance(run_result.get("hard_checks"), dict) else {}
    if hard_checks:
        return bool(
            hard_checks.get("check_model_pass")
            and hard_checks.get("simulate_pass")
            and hard_checks.get("physics_contract_pass", True)
            and hard_checks.get("regression_pass", True)
        )
    return bool(
        run_result.get("check_model_pass")
        and run_result.get("simulate_pass")
        and run_result.get("physics_contract_pass", True)
        and run_result.get("regression_pass", True)
    )


def _count_applied_rule_actions(run_result: dict, action_rows: list[dict] | None = None) -> int:
    if isinstance(action_rows, list):
        return len([row for row in action_rows if isinstance(row, dict) and (row.get("rule_id") or row.get("action_key"))])
    count = 0
    for attempt in _attempts(run_result):
        for value in attempt.values():
            if isinstance(value, dict) and bool(value.get("applied")) and (value.get("rule_id") or value.get("action_key")):
                count += 1
    return count


def resolve_dominant_stage_subtype(run_result: dict) -> str:
    direct = str(run_result.get("dominant_stage_subtype") or run_result.get("stage_subtype") or "").strip()
    if direct:
        return direct

    values: list[str] = []
    for attempt in _attempts(run_result):
        diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
        subtype = str(diagnostic.get("dominant_stage_subtype") or diagnostic.get("stage_subtype") or "").strip()
        if not subtype:
            subtype = dominant_stage_subtype_v0(
                error_type=str(diagnostic.get("error_type") or ""),
                error_subtype=str(diagnostic.get("error_subtype") or ""),
                observed_phase=str(diagnostic.get("observed_phase") or diagnostic.get("stage") or ""),
            )
        if subtype and subtype != "stage_0_none":
            values.append(subtype)
    if not values:
        diagnostic = run_result.get("diagnostic_ir") if isinstance(run_result.get("diagnostic_ir"), dict) else {}
        subtype = str(diagnostic.get("dominant_stage_subtype") or diagnostic.get("stage_subtype") or "").strip()
        if not subtype:
            subtype = dominant_stage_subtype_v0(
                error_type=str(diagnostic.get("error_type") or ""),
                error_subtype=str(diagnostic.get("error_subtype") or ""),
                observed_phase=str(diagnostic.get("observed_phase") or diagnostic.get("stage") or ""),
            )
        return subtype or "stage_0_none"

    counts = Counter(values)
    best_value = "stage_0_none"
    best_count = -1
    best_last_idx = -1
    for value, count in counts.items():
        last_idx = max(idx for idx, item in enumerate(values) if item == value)
        if count > best_count or (count == best_count and last_idx > best_last_idx):
            best_value = value
            best_count = count
            best_last_idx = last_idx
    return best_value


def _planner_invoked(run_result: dict) -> bool:
    if int(run_result.get("llm_request_count_delta") or 0) > 0:
        return True
    if bool(run_result.get("llm_plan_generated")) or bool(run_result.get("llm_plan_used")):
        return True
    if str(run_result.get("planner_request_kind") or "").strip():
        return True
    for attempt in _attempts(run_result):
        if isinstance(attempt.get("planner_experience_injection"), dict):
            return True
    return False


def _planner_used(run_result: dict) -> bool:
    planner = run_result.get("planner_experience_injection") if isinstance(run_result.get("planner_experience_injection"), dict) else {}
    if bool(planner.get("used")):
        return True
    return bool(
        run_result.get("llm_plan_generated")
        or run_result.get("llm_plan_used")
        or run_result.get("llm_plan_parsed")
        or run_result.get("planner_request_kind")
    )


def _planner_decisive_weak(run_result: dict, *, planner_used: bool) -> tuple[bool, str]:
    if not _success(run_result) or not planner_used:
        return False, "planner_not_decisive"
    if bool(run_result.get("llm_plan_was_decisive")):
        return True, "llm_plan_was_decisive"
    if bool(run_result.get("llm_only_resolution")):
        return True, "llm_only_resolution"
    primary = str(run_result.get("resolution_primary_contribution") or "").strip().lower()
    if primary in {"llm_first_plan", "llm_replan", "switch_branch_replan", "guided_search_decisive"}:
        return True, primary
    if bool(run_result.get("llm_plan_helped_resolution")) and bool(run_result.get("llm_resolution_contributed")):
        return True, "llm_helped_resolution_proxy"
    return False, "planner_contribution_not_observed"


def _replay_used(run_result: dict) -> bool:
    replay = run_result.get("experience_replay") if isinstance(run_result.get("experience_replay"), dict) else {}
    if bool(replay.get("used")):
        return True
    for attempt in _attempts(run_result):
        attempt_replay = attempt.get("experience_replay") if isinstance(attempt.get("experience_replay"), dict) else {}
        if bool(attempt_replay.get("used")):
            return True
    return False


def build_resolution_attribution(run_result: dict, *, action_rows: list[dict] | None = None) -> dict:
    deterministic_rule_applied_count = _count_applied_rule_actions(run_result, action_rows=action_rows)
    planner_invoked = _planner_invoked(run_result)
    planner_used = _planner_used(run_result)
    planner_decisive, planner_decisive_reason = _planner_decisive_weak(run_result, planner_used=planner_used)
    replay_used = _replay_used(run_result)
    dominant_stage_subtype = resolve_dominant_stage_subtype(run_result)
    llm_request_count = int(run_result.get("llm_request_count_delta") or run_result.get("live_request_count") or 0)

    if not _success(run_result):
        resolution_path = "unresolved"
    elif planner_decisive:
        resolution_path = "llm_planner_assisted"
    elif planner_invoked and deterministic_rule_applied_count > 0:
        resolution_path = "rule_then_llm"
    elif planner_invoked:
        resolution_path = "llm_planner_assisted"
    else:
        resolution_path = "deterministic_rule_only"

    return {
        "schema_version": SCHEMA_VERSION,
        "resolution_path": resolution_path,
        "planner_invoked": planner_invoked,
        "planner_used": planner_used,
        "planner_decisive": planner_decisive,
        "planner_decisive_reason": planner_decisive_reason,
        "planner_decisive_method": "weak_supervision_proxy_heuristic",
        "replay_used": replay_used,
        "deterministic_rule_applied_count": deterministic_rule_applied_count,
        "llm_request_count": llm_request_count,
        "dominant_stage_subtype": dominant_stage_subtype,
    }
