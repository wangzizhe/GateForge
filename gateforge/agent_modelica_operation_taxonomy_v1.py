from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Operation class constants
# ---------------------------------------------------------------------------

OP_CLASS_READ_ONLY = "read_only"
OP_CLASS_MUTATING = "mutating"
OP_CLASS_DESTRUCTIVE = "destructive"


# ---------------------------------------------------------------------------
# OperationSpec — stable fact layer
#
# Records objective, unchanging properties of a GateForge internal operation.
# No policy, no profile-sensitivity, no execution logic here.
#
# Fields:
#   name               — canonical operation identifier
#   op_class           — coarse risk class: read_only / mutating / destructive
#   mutates_candidate  — writes to the candidate model file
#   mutates_workspace  — writes to the OMC workspace (tmp dirs, artifacts)
#   requires_exclusive — must not run concurrently with any other operation
#   consumes_budget    — consumes LLM token budget or significant compute
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationSpec:
    name: str
    op_class: str
    mutates_candidate: bool
    mutates_workspace: bool
    requires_exclusive: bool
    consumes_budget: bool


# ---------------------------------------------------------------------------
# OPERATION_REGISTRY
#
# Source of truth for all known GateForge internal operations.
# Add new operations here as they are formalised.
# ---------------------------------------------------------------------------

OPERATION_REGISTRY: dict[str, OperationSpec] = {
    "omc_check": OperationSpec(
        name="omc_check",
        op_class=OP_CLASS_READ_ONLY,
        mutates_candidate=False,
        mutates_workspace=False,
        requires_exclusive=False,
        consumes_budget=False,
    ),
    "omc_simulate": OperationSpec(
        name="omc_simulate",
        op_class=OP_CLASS_READ_ONLY,
        mutates_candidate=False,
        mutates_workspace=False,
        requires_exclusive=False,
        consumes_budget=False,
    ),
    "replay_lookup": OperationSpec(
        name="replay_lookup",
        op_class=OP_CLASS_READ_ONLY,
        mutates_candidate=False,
        mutates_workspace=False,
        requires_exclusive=False,
        consumes_budget=False,
    ),
    "planner_invoke": OperationSpec(
        name="planner_invoke",
        op_class=OP_CLASS_MUTATING,
        mutates_candidate=False,
        mutates_workspace=False,
        requires_exclusive=False,
        consumes_budget=True,
    ),
    "apply_repair": OperationSpec(
        name="apply_repair",
        op_class=OP_CLASS_MUTATING,
        mutates_candidate=True,
        mutates_workspace=True,
        requires_exclusive=True,   # writes candidate file; must not run concurrently
        consumes_budget=False,
    ),
    "restore_source": OperationSpec(
        name="restore_source",
        op_class=OP_CLASS_DESTRUCTIVE,
        mutates_candidate=True,
        mutates_workspace=True,
        requires_exclusive=True,
        consumes_budget=False,
    ),
}


def get_operation(name: str) -> OperationSpec:
    """Return the OperationSpec for *name*, raising KeyError if unknown."""
    return OPERATION_REGISTRY[name]


def all_operations() -> list[OperationSpec]:
    """Return all registered operations in stable insertion order."""
    return list(OPERATION_REGISTRY.values())
