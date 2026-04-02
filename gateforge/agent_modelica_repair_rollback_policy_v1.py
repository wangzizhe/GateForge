from __future__ import annotations

# ---------------------------------------------------------------------------
# Repair rollback policy — pure decision function
#
# Determines whether the executor should roll back current_text to its
# pre-round checkpoint after a repair attempt.
#
# Design constraints:
#   - pure function, no I/O, no OMC, no LLM
#   - all inputs are signals already available in the executor repair loop
#   - no continuous behavioral score is assumed; only boolean / count signals
#
# Rollback trigger hierarchy (any one True → rollback):
#   1. Execution regression  — check_ok or simulate_ok dropped (compilation
#                              or simulation that previously passed now fails)
#   2. Contract regression   — physics_contract_pass dropped True → False
#   3. Scenario regression   — fewer scenarios pass than before the repair
#                              (catches partial-pass degradation invisible to
#                              the aggregate contract boolean)
#
# Usage in executor repair loop:
#
#   pre_check_ok = round_result.get("check_ok", False)
#   pre_simulate_ok = round_result.get("simulate_ok", False)
#   # ... apply repair ...
#   if should_rollback(
#       pre_check_ok=pre_check_ok,
#       post_check_ok=new_check_ok,
#       pre_simulate_ok=pre_simulate_ok,
#       post_simulate_ok=new_simulate_ok,
#       pre_contract_pass=pre_contract_pass,
#       post_contract_pass=new_contract_pass,
#       pre_scenario_pass_count=pre_scenario_count,
#       post_scenario_pass_count=new_scenario_count,
#   ):
#       current_text = mgr.restore_at_round(round_idx)
#
# ---------------------------------------------------------------------------

_REASON_NONE = "none"
_REASON_CHECK_REGRESSION = "check_regression"
_REASON_SIMULATE_REGRESSION = "simulate_regression"
_REASON_CONTRACT_REGRESSION = "contract_regression"
_REASON_SCENARIO_REGRESSION = "scenario_regression"


def should_rollback(
    *,
    pre_check_ok: bool,
    post_check_ok: bool,
    pre_simulate_ok: bool | None = None,
    post_simulate_ok: bool | None = None,
    pre_contract_pass: bool | None = None,
    post_contract_pass: bool | None = None,
    pre_scenario_pass_count: int | None = None,
    post_scenario_pass_count: int | None = None,
) -> bool:
    """Return True if the repair round should be rolled back.

    Parameters
    ----------
    pre_check_ok:
        Whether the model compiled successfully *before* the repair.
    post_check_ok:
        Whether the model compiles successfully *after* the repair.
    pre_simulate_ok:
        Whether the model simulated successfully before the repair.
        Pass None (default) when simulation was not run at this stage
        (e.g. compilation failed and simulation was skipped).  Passing
        None disables the simulate_regression check explicitly rather than
        silently — do not pass False to mean "not evaluated."
    post_simulate_ok:
        Whether the model simulates successfully after the repair.
        Same None semantics as pre_simulate_ok.
    pre_contract_pass:
        Whether the physics contract passed before the repair, or None
        if the contract was not evaluated (e.g. model did not compile).
    post_contract_pass:
        Whether the physics contract passes after the repair, or None.
    pre_scenario_pass_count:
        Number of contract scenarios that passed before the repair, or None.
        Only meaningful if pre_contract_pass is available.
    post_scenario_pass_count:
        Number of contract scenarios that pass after the repair, or None.

    Returns
    -------
    True if any regression condition is detected; False if no rollback needed.
    """
    return rollback_reason(
        pre_check_ok=pre_check_ok,
        post_check_ok=post_check_ok,
        pre_simulate_ok=pre_simulate_ok,
        post_simulate_ok=post_simulate_ok,
        pre_contract_pass=pre_contract_pass,
        post_contract_pass=post_contract_pass,
        pre_scenario_pass_count=pre_scenario_pass_count,
        post_scenario_pass_count=post_scenario_pass_count,
    ) != _REASON_NONE


def rollback_reason(
    *,
    pre_check_ok: bool,
    post_check_ok: bool,
    pre_simulate_ok: bool | None = None,
    post_simulate_ok: bool | None = None,
    pre_contract_pass: bool | None = None,
    post_contract_pass: bool | None = None,
    pre_scenario_pass_count: int | None = None,
    post_scenario_pass_count: int | None = None,
) -> str:
    """Return a reason string explaining why rollback was triggered.

    Returns _REASON_NONE ("none") if no rollback is needed.
    Returns the first matching regression reason string otherwise.

    Useful for logging and audit: the executor can record which condition
    triggered the rollback without re-running the decision logic.
    """
    # 1. Compilation regression
    if pre_check_ok and not post_check_ok:
        return _REASON_CHECK_REGRESSION

    # 2. Simulation regression — only checked when both sides were evaluated.
    #    None means "simulation was not run at this stage" (e.g. compile failed).
    #    We require both sides to be non-None; a single None means we cannot
    #    determine whether a regression occurred and we skip this check.
    if (
        pre_simulate_ok is not None
        and post_simulate_ok is not None
        and pre_simulate_ok
        and not post_simulate_ok
    ):
        return _REASON_SIMULATE_REGRESSION

    # 3. Physics contract regression (aggregate boolean)
    if pre_contract_pass is True and post_contract_pass is False:
        return _REASON_CONTRACT_REGRESSION

    # 4. Scenario count regression (catches partial-pass degradation)
    if (
        pre_scenario_pass_count is not None
        and post_scenario_pass_count is not None
        and post_scenario_pass_count < pre_scenario_pass_count
    ):
        return _REASON_SCENARIO_REGRESSION

    return _REASON_NONE


# ---------------------------------------------------------------------------
# Public constants — for callers that need to match on reason strings
# ---------------------------------------------------------------------------

ROLLBACK_REASON_NONE = _REASON_NONE
ROLLBACK_REASON_CHECK_REGRESSION = _REASON_CHECK_REGRESSION
ROLLBACK_REASON_SIMULATE_REGRESSION = _REASON_SIMULATE_REGRESSION
ROLLBACK_REASON_CONTRACT_REGRESSION = _REASON_CONTRACT_REGRESSION
ROLLBACK_REASON_SCENARIO_REGRESSION = _REASON_SCENARIO_REGRESSION
