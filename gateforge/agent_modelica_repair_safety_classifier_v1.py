from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Repair Safety Classifier — negative-direction pre-apply gate
#
# Checks a proposed repair text against a set of high-confidence dangerous
# anti-patterns BEFORE the repair is applied to the candidate model.
#
# This is complementary to the behavioral contract evaluator (which runs
# post-apply, after OMC checks pass) and to _guard_robustness_patch (which
# is domain-specific to one repair family).
#
# Design constraints:
#   - pure functions, no I/O, no OMC, no LLM
#   - fail-safe: unknown operations default to SAFE (classifier is
#     additive, not a replacement for OMC validation)
#   - only high-confidence patterns in the registry; prefer false-negative
#     (miss a dangerous repair) over false-positive (block a good repair)
#
# Verdict levels:
#   safe          — no dangerous patterns detected; proceed with apply_repair
#   needs_review  — suspicious pattern; downgrade from auto-apply to gated
#   reject        — high-confidence structural damage; block outright
#
# Profile awareness:
#   default       — standard thresholds
#   planner_heavy — lower thresholds on structural checks (LLM-proposed
#                   repairs carry higher structural-damage risk on harder lanes)
# ---------------------------------------------------------------------------

VERDICT_SAFE = "safe"
VERDICT_NEEDS_REVIEW = "needs_review"
VERDICT_REJECT = "reject"

_VERDICT_ORDER = {VERDICT_SAFE: 0, VERDICT_NEEDS_REVIEW: 1, VERDICT_REJECT: 2}


@dataclass(frozen=True)
class SafetyViolation:
    pattern_id: str
    description: str
    verdict: str    # "needs_review" | "reject"
    detail: str = ""


@dataclass(frozen=True)
class RepairSafetyResult:
    """Result of a repair safety classification."""

    verdict: str                            # aggregate verdict
    violations: tuple[SafetyViolation, ...]
    original_line_count: int
    proposed_line_count: int
    original_char_count: int
    proposed_char_count: int
    profile: str

    @property
    def is_safe(self) -> bool:
        return self.verdict == VERDICT_SAFE

    @property
    def violation_ids(self) -> list[str]:
        return [v.pattern_id for v in self.violations]

    def summary(self) -> dict:
        return {
            "verdict": self.verdict,
            "is_safe": self.is_safe,
            "violation_count": len(self.violations),
            "violation_ids": self.violation_ids,
            "original_line_count": self.original_line_count,
            "proposed_line_count": self.proposed_line_count,
            "original_char_count": self.original_char_count,
            "proposed_char_count": self.proposed_char_count,
            "profile": self.profile,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _primary_model_name(text: str) -> str:
    """Extract the first top-level model name from Modelica text."""
    match = re.search(r"^\s*(?:model|block|connector|record|package)\s+(\w+)", text, re.MULTILINE)
    return match.group(1) if match else ""


def _count_pattern(pattern: str, text: str, flags: int = 0) -> int:
    return len(re.findall(pattern, text, flags))


def _has_equation_section(text: str) -> bool:
    """True if the text contains an 'equation' keyword at statement level."""
    return bool(re.search(r"^\s*equation\b", text, re.MULTILINE))


def _has_initial_equation_section(text: str) -> bool:
    return bool(re.search(r"^\s*initial\s+equation\b", text, re.MULTILINE))


def _count_connect_statements(text: str) -> int:
    return _count_pattern(r"\bconnect\s*\(", text)


def _count_parameter_declarations(text: str) -> int:
    return _count_pattern(r"\bparameter\s+\w", text)


def _shrink_ratio(original: str, proposed: str) -> float:
    """Ratio of proposed length to original length (0.0–1.0+)."""
    orig_len = len(original.strip())
    if orig_len == 0:
        return 1.0
    return len(proposed.strip()) / orig_len


# ---------------------------------------------------------------------------
# Pattern checkers
# Each returns a SafetyViolation or None.
# ---------------------------------------------------------------------------


def _check_empty_repair(original: str, proposed: str, profile: str) -> SafetyViolation | None:
    """EMPTY_REPAIR: proposed text is empty or pure whitespace."""
    if not proposed.strip():
        return SafetyViolation(
            pattern_id="EMPTY_REPAIR",
            description="Proposed repair is empty or whitespace only.",
            verdict=VERDICT_REJECT,
            detail=f"proposed_char_count={len(proposed)}",
        )
    return None


def _check_model_emptied(original: str, proposed: str, profile: str) -> SafetyViolation | None:
    """MODEL_EMPTIED: proposed text is drastically shorter than original.

    Threshold: <20% of original length (default) or <30% (planner_heavy).
    Catches wholesale deletion of model body by LLM.
    """
    threshold = 0.30 if profile == "planner_heavy" else 0.20
    ratio = _shrink_ratio(original, proposed)
    if ratio < threshold:
        return SafetyViolation(
            pattern_id="MODEL_EMPTIED",
            description="Proposed repair is drastically shorter than the original.",
            verdict=VERDICT_REJECT,
            detail=f"shrink_ratio={ratio:.2f} threshold={threshold}",
        )
    return None


def _check_model_name_changed(original: str, proposed: str, profile: str) -> SafetyViolation | None:
    """MODEL_NAME_CHANGED: primary model class name differs.

    A rename almost always indicates the LLM hallucinated a new model
    rather than repairing the existing one.
    """
    orig_name = _primary_model_name(original)
    prop_name = _primary_model_name(proposed)
    if orig_name and prop_name and orig_name != prop_name:
        return SafetyViolation(
            pattern_id="MODEL_NAME_CHANGED",
            description="Primary model name changed by the repair.",
            verdict=VERDICT_REJECT,
            detail=f"original='{orig_name}' proposed='{prop_name}'",
        )
    return None


def _check_equation_block_removed(original: str, proposed: str, profile: str) -> SafetyViolation | None:
    """EQUATION_BLOCK_REMOVED: original had an equation section; proposed does not.

    Removing the equation section destroys all dynamics and connections.
    """
    if _has_equation_section(original) and not _has_equation_section(proposed):
        return SafetyViolation(
            pattern_id="EQUATION_BLOCK_REMOVED",
            description="The 'equation' section was removed by the repair.",
            verdict=VERDICT_REJECT,
        )
    return None


def _check_initial_equation_removed(original: str, proposed: str, profile: str) -> SafetyViolation | None:
    """INITIAL_EQUATION_REMOVED: original had initial equation; proposed does not.

    Removing initial equations can break initialization and cause OMC to
    produce different (often wrong) initial conditions.
    Severity: needs_review (sometimes intentional for over-constrained systems).
    """
    if _has_initial_equation_section(original) and not _has_initial_equation_section(proposed):
        return SafetyViolation(
            pattern_id="INITIAL_EQUATION_REMOVED",
            description="The 'initial equation' section was removed by the repair.",
            verdict=VERDICT_NEEDS_REVIEW,
        )
    return None


def _check_connect_mass_deletion(original: str, proposed: str, profile: str) -> SafetyViolation | None:
    """CONNECT_MASS_DELETION: >60% of connect() statements removed.

    Threshold is lowered to >40% under planner_heavy profile.
    Losing most connections breaks the physical model topology.
    """
    orig_count = _count_connect_statements(original)
    if orig_count < 2:
        return None  # too few to be meaningful
    prop_count = _count_connect_statements(proposed)
    deletion_ratio = (orig_count - prop_count) / orig_count
    threshold = 0.40 if profile == "planner_heavy" else 0.60
    if deletion_ratio > threshold:
        return SafetyViolation(
            pattern_id="CONNECT_MASS_DELETION",
            description="More than half of connect() statements were removed.",
            verdict=VERDICT_REJECT,
            detail=(
                f"original_connect_count={orig_count} "
                f"proposed_connect_count={prop_count} "
                f"deletion_ratio={deletion_ratio:.2f}"
            ),
        )
    return None


def _check_parameter_mass_demotion(original: str, proposed: str, profile: str) -> SafetyViolation | None:
    """PARAMETER_MASS_DEMOTION: >50% of parameter declarations removed.

    Threshold is lowered to >30% under planner_heavy profile.
    Removing parameter keywords turns physical constants into free variables,
    which usually causes algebraic singularities or wrong simulation results.
    """
    orig_count = _count_parameter_declarations(original)
    if orig_count < 2:
        return None  # too few to be meaningful
    prop_count = _count_parameter_declarations(proposed)
    deletion_ratio = (orig_count - prop_count) / orig_count
    threshold = 0.30 if profile == "planner_heavy" else 0.50
    if deletion_ratio > threshold:
        return SafetyViolation(
            pattern_id="PARAMETER_MASS_DEMOTION",
            description="A large fraction of parameter declarations were removed.",
            verdict=VERDICT_NEEDS_REVIEW,
            detail=(
                f"original_parameter_count={orig_count} "
                f"proposed_parameter_count={prop_count} "
                f"deletion_ratio={deletion_ratio:.2f}"
            ),
        )
    return None


# ---------------------------------------------------------------------------
# Pattern registry — ordered list of checker functions
# Add new checkers here; order determines evaluation priority.
# ---------------------------------------------------------------------------

_PATTERN_CHECKERS = [
    _check_empty_repair,
    _check_model_emptied,
    _check_model_name_changed,
    _check_equation_block_removed,
    _check_initial_equation_removed,
    _check_connect_mass_deletion,
    _check_parameter_mass_demotion,
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_repair_safety(
    original_text: str,
    proposed_text: str,
    profile: str = "default",
) -> RepairSafetyResult:
    """Classify whether *proposed_text* is safe to apply as a repair.

    Parameters
    ----------
    original_text:
        The candidate model text before the repair is applied.
    proposed_text:
        The repaired model text proposed by the rule engine or LLM.
    profile:
        Execution profile affecting thresholds.
        ``"planner_heavy"`` applies stricter thresholds because LLM-proposed
        repairs on harder lanes carry higher structural-damage risk.

    Returns
    -------
    RepairSafetyResult with aggregate verdict and all triggered violations.
    """
    original = str(original_text or "")
    proposed = str(proposed_text or "")

    violations: list[SafetyViolation] = []
    for checker in _PATTERN_CHECKERS:
        result = checker(original, proposed, profile)
        if result is not None:
            violations.append(result)

    # Aggregate to the highest-severity verdict
    if violations:
        worst = max(violations, key=lambda v: _VERDICT_ORDER[v.verdict])
        aggregate_verdict = worst.verdict
    else:
        aggregate_verdict = VERDICT_SAFE

    return RepairSafetyResult(
        verdict=aggregate_verdict,
        violations=tuple(violations),
        original_line_count=len(original.splitlines()),
        proposed_line_count=len(proposed.splitlines()),
        original_char_count=len(original),
        proposed_char_count=len(proposed),
        profile=profile,
    )


def is_safe_to_apply(
    original_text: str,
    proposed_text: str,
    profile: str = "default",
) -> bool:
    """Convenience wrapper — True only if verdict is SAFE.

    Use when the caller only needs a boolean gate and not the full result.
    """
    return classify_repair_safety(original_text, proposed_text, profile).verdict == VERDICT_SAFE
