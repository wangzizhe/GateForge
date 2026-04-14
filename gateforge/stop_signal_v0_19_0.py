from __future__ import annotations

import re

HARD_CAP_TURNS = 8
STALLED_CONSECUTIVE = 2
CYCLING_JACCARD_THRESHOLD = 0.85


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _patch_tokens(patch: str) -> frozenset[str]:
    tokens: list[str] = []
    for line in patch.splitlines():
        if not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
            continue
        # strip leading +/- marker
        content = line[1:]
        # strip inline // comments
        content = re.sub(r"//.*", "", content)
        tokens.extend(content.split())
    return frozenset(tokens)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def check_timeout(turn_id: int) -> bool:
    """Returns True if turn_id has reached or exceeded the hard cap."""
    return turn_id >= HARD_CAP_TURNS


def check_stalled(current_error: str, prior_errors: list[str]) -> bool:
    """Returns True when the current turn repeats the immediately prior normalized error,
    satisfying the 2-consecutive stalled rule (STALLED_CONSECUTIVE = 2).
    If STALLED_CONSECUTIVE is ever changed, this function's logic must be updated accordingly."""
    if len(prior_errors) < 1:
        return False
    return _normalize(current_error) == _normalize(prior_errors[-1])


def check_cycling(current_patch: str, prior_patches: list[str]) -> bool:
    """Returns True if current patch Jaccard similarity > threshold against any prior patch.

    Similarity is computed over normalized changed-line tokens extracted from diff hunks only,
    not the raw full LLM response.
    """
    current_tokens = _patch_tokens(current_patch)
    for prior in prior_patches:
        prior_tokens = _patch_tokens(prior)
        if _jaccard(current_tokens, prior_tokens) > CYCLING_JACCARD_THRESHOLD:
            return True
    return False


def check_stop(
    turn_id: int,
    current_error: str,
    current_patch: str,
    prior_errors: list[str],
    prior_patches: list[str],
) -> tuple[bool, str | None]:
    """Unified stop dispatcher. Returns (should_stop, reason).

    reason is one of: 'timeout', 'stalled', 'cycling', or None if no stop.
    Conditions are evaluated in priority order: timeout > stalled > cycling.
    """
    if check_timeout(turn_id):
        return True, "timeout"
    if check_stalled(current_error, prior_errors):
        return True, "stalled"
    if check_cycling(current_patch, prior_patches):
        return True, "cycling"
    return False, None


__all__ = [
    "CYCLING_JACCARD_THRESHOLD",
    "HARD_CAP_TURNS",
    "STALLED_CONSECUTIVE",
    "check_cycling",
    "check_stalled",
    "check_stop",
    "check_timeout",
]
