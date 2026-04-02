from __future__ import annotations

from .agent_modelica_operation_taxonomy_v1 import (
    OP_CLASS_DESTRUCTIVE,
    OP_CLASS_MUTATING,
    OperationSpec,
)

# ---------------------------------------------------------------------------
# Operation policy — derived layer
#
# All functions here derive control decisions purely from taxonomy facts.
# No hardcoded operation names; decisions follow from OperationSpec fields.
#
# Profile-sensitive overrides live in this layer (profile: str argument).
# Known profiles:
#   "default"        — standard GateForge repair run
#   "planner_heavy"  — planner is primary repair driver (harder lanes)
#   "rule_only"      — deterministic rules only, no planner
#   "evidence_verifier" — read-only audit role, no repair actions
# ---------------------------------------------------------------------------


def requires_checkpoint(spec: OperationSpec) -> bool:
    """True if a repair-state checkpoint must be captured before this operation.

    Applies to any operation that writes candidate or workspace state, so that
    dirty-state rollback is possible if the operation or its downstream check
    fails.
    """
    return spec.mutates_candidate or spec.mutates_workspace


def requires_safety_gate(spec: OperationSpec, profile: str = "default") -> bool:
    """True if this operation must pass a safety classifier before execution.

    Destructive operations always require a gate regardless of profile.
    Under planner_heavy profile, any candidate-mutating operation is also gated
    because LLM-proposed repairs carry higher structural-damage risk.
    """
    if spec.op_class == OP_CLASS_DESTRUCTIVE:
        return True
    if profile == "planner_heavy" and spec.mutates_candidate:
        return True
    return False


def allows_concurrency(spec: OperationSpec) -> bool:
    """True if this operation may run concurrently alongside other operations.

    Exclusive operations (write candidate or require workspace lock) must run
    alone.  Read-only operations are always safe to batch.

    IMPORTANT — scope of this predicate:
        This function only answers "is the operation safe to run concurrently
        across *independent tasks* with isolated workspaces?"  It does NOT
        imply that concurrent execution within a *single task sharing executor
        state* is safe.  In a shared-state repair loop (one candidate file,
        one CheckpointManager) concurrent mutating operations would race
        regardless of this flag.  Do not use this predicate to authorise
        same-task concurrency.
    """
    return not spec.requires_exclusive


def is_verifier_visible(spec: OperationSpec) -> bool:
    """True if this operation should leave an audit trail for the verifier role.

    Any operation that changes candidate or workspace state must be recorded
    so the independent verifier can reconstruct the repair sequence.
    """
    return spec.mutates_candidate or spec.mutates_workspace or spec.op_class == OP_CLASS_DESTRUCTIVE


def is_budget_tracked(spec: OperationSpec) -> bool:
    """True if this operation's invocation should be counted against budget."""
    return spec.consumes_budget or spec.op_class in (OP_CLASS_MUTATING, OP_CLASS_DESTRUCTIVE)


def is_planner_event(spec: OperationSpec) -> bool:
    """True if this operation represents a planner decision event.

    Planner events are those that invoke LLM reasoning to generate or select
    a repair action.  They do not directly mutate candidate or workspace state
    (hence is_verifier_visible returns False for them), but they should still
    be tracked separately so the verifier can audit the decision sequence.

    This is a distinct signal from is_verifier_visible:
        is_verifier_visible  — tracks file/state changes (mutating / destructive)
        is_planner_event     — tracks LLM decision invocations (no file change)

    Both may be True for the same operation in future, but currently they cover
    disjoint sets: planner_invoke is a planner event but not verifier-visible;
    apply_repair is verifier-visible but not a planner event.

    KNOWN LIMITATION — consumes_budget as proxy:
        This function currently uses spec.consumes_budget as the planner-event
        signal.  That is correct for the current 6-operation registry where
        only planner_invoke has consumes_budget=True.  However, if a future
        compute-heavy non-planner operation (e.g. a heavy static analyser) is
        also marked consumes_budget=True, it would be incorrectly classified as
        a planner event.  If that case arises, the fix is to add a dedicated
        is_planner_event: bool field to OperationSpec rather than continuing to
        derive from consumes_budget.
    """
    return spec.consumes_budget  # proxy — valid for current registry; see limitation above


def operation_summary(spec: OperationSpec, profile: str = "default") -> dict:
    """Return a compact policy summary dict for logging and audit."""
    return {
        "name": spec.name,
        "op_class": spec.op_class,
        "requires_checkpoint": requires_checkpoint(spec),
        "requires_safety_gate": requires_safety_gate(spec, profile),
        "allows_concurrency": allows_concurrency(spec),
        "is_verifier_visible": is_verifier_visible(spec),
        "is_budget_tracked": is_budget_tracked(spec),
        "is_planner_event": is_planner_event(spec),
    }
