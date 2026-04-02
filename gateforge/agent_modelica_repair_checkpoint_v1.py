from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from .agent_modelica_operation_policy_v1 import requires_checkpoint
from .agent_modelica_operation_taxonomy_v1 import OPERATION_REGISTRY, OperationSpec

# ---------------------------------------------------------------------------
# RepairCheckpoint — candidate-text checkpoint (NOT a full repair-state snapshot)
#
# Captures the candidate model text at a single point in the repair loop,
# before a mutating or destructive operation is applied.
#
# Scope — what IS covered:
#   model_text      — the candidate Modelica source string (authoritative state)
#
# Scope — what is NOT covered (by design):
#   OMC workspace   — workspace is derived from current_text and overwritten at
#                     each round start; no separate workspace snapshot is needed
#   attempts list   — audit log of past actions; not rolled back, only appended
#   round counter   — monotonically increasing; rollback does not reset it
#   executor flags  — check_ok, simulate_ok, contract_pass from prior rounds
#
# Rationale:
#   current_text is the sole mutable authoritative state in the repair loop.
#   All other state is either derived (workspace) or append-only audit (attempts).
#   Rolling back current_text is sufficient to restart a round cleanly.
#
# Fields:
#   round_number    — which repair round this was captured in (1-indexed)
#   pre_operation   — name of the operation that is about to be applied
#   model_text      — the candidate model text at capture time
#   captured_at_sec — monotonic timestamp for ordering and audit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepairCheckpoint:
    round_number: int
    pre_operation: str
    model_text: str
    captured_at_sec: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# Standalone helpers — no class required for simple cases
# ---------------------------------------------------------------------------


def make_checkpoint(
    round_number: int,
    pre_operation: str,
    model_text: str,
) -> RepairCheckpoint:
    """Capture a checkpoint before *pre_operation* is applied in *round_number*."""
    return RepairCheckpoint(
        round_number=round_number,
        pre_operation=pre_operation,
        model_text=model_text,
        captured_at_sec=time.monotonic(),
    )


def checkpoint_text(checkpoint: RepairCheckpoint) -> str:
    """Return the model text stored in *checkpoint*."""
    return checkpoint.model_text


def should_capture_before(operation_name: str) -> bool:
    """True if a checkpoint must be captured before *operation_name*.

    Derived from the taxonomy policy: any operation that mutates candidate or
    workspace state requires a prior checkpoint so dirty-state rollback is
    possible.  Unknown operations are treated as checkpoint-required (fail-safe).
    """
    spec = OPERATION_REGISTRY.get(operation_name)
    if spec is None:
        return True  # unknown operations are fail-safe: always checkpoint
    return requires_checkpoint(spec)


def checkpoint_summary(checkpoint: RepairCheckpoint) -> dict:
    """Return a compact audit dict for logging."""
    return {
        "round_number": checkpoint.round_number,
        "pre_operation": checkpoint.pre_operation,
        "model_text_len": len(checkpoint.model_text),
        "captured_at_sec": round(checkpoint.captured_at_sec, 4),
    }


# ---------------------------------------------------------------------------
# CheckpointManager — rolling window of recent checkpoints
#
# Maintains up to *max_retained* checkpoints.  Older checkpoints are evicted
# automatically when the window is full.  The manager is intended to be
# instantiated once per repair run, not shared across runs.
# ---------------------------------------------------------------------------


class CheckpointManager:
    """Rolling window checkpoint manager for one repair run."""

    def __init__(self, max_retained: int = 3) -> None:
        if max_retained < 1:
            raise ValueError(f"max_retained must be >= 1, got {max_retained}")
        self._max = max_retained
        self._stack: list[RepairCheckpoint] = []

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def capture(
        self,
        round_number: int,
        pre_operation: str,
        model_text: str,
    ) -> RepairCheckpoint:
        """Capture a new checkpoint and add it to the window.

        If the window is full, the oldest checkpoint is evicted first.
        Returns the newly captured checkpoint.
        """
        cp = make_checkpoint(round_number, pre_operation, model_text)
        if len(self._stack) >= self._max:
            self._stack.pop(0)
        self._stack.append(cp)
        return cp

    def capture_if_needed(
        self,
        round_number: int,
        operation_name: str,
        model_text: str,
    ) -> Optional[RepairCheckpoint]:
        """Capture a checkpoint only if the taxonomy policy requires it.

        Returns the checkpoint if captured, None otherwise.
        Callers may ignore the return value if they only need the side-effect.
        """
        if should_capture_before(operation_name):
            return self.capture(round_number, operation_name, model_text)
        return None

    def clear(self) -> None:
        """Discard all retained checkpoints."""
        self._stack.clear()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def latest(self) -> Optional[RepairCheckpoint]:
        """Return the most recently captured checkpoint, or None."""
        return self._stack[-1] if self._stack else None

    def at_round(self, round_number: int) -> Optional[RepairCheckpoint]:
        """Return the most recent checkpoint captured in *round_number*, or None."""
        for cp in reversed(self._stack):
            if cp.round_number == round_number:
                return cp
        return None

    def restore_latest(self) -> Optional[str]:
        """Return the model text from the latest checkpoint.

        Does not remove the checkpoint from the window — restoring does not
        consume the checkpoint, so the same checkpoint can be inspected again.
        Returns None if no checkpoint has been captured yet.
        """
        cp = self.latest()
        return cp.model_text if cp is not None else None

    def restore_at_round(self, round_number: int) -> Optional[str]:
        """Return the model text from the most recent checkpoint for *round_number*.

        Returns None if no checkpoint exists for that round.
        """
        cp = self.at_round(round_number)
        return cp.model_text if cp is not None else None

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    @property
    def depth(self) -> int:
        """Number of checkpoints currently retained."""
        return len(self._stack)

    def summary(self) -> dict:
        """Return an audit-friendly summary of the current window."""
        return {
            "depth": self.depth,
            "max_retained": self._max,
            "checkpoints": [checkpoint_summary(cp) for cp in self._stack],
            "latest_round": self._stack[-1].round_number if self._stack else None,
            "latest_operation": self._stack[-1].pre_operation if self._stack else None,
        }
