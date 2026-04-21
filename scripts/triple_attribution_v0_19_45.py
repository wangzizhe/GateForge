"""Triple underdetermined per-turn attribution core (v0.19.45).

Two-level root-cause state classification for triple compound trajectories:

  Level 1 — Structural (checkModel):
    not_attempted          — no observable action on this root cause
    attempted_incomplete    — directionally correct but execution incomplete
    structural_fixed        — structural balance restored (checkModel PASS)

  Level 2 — Behavioral (simulate):
    structural_fixed_behavioral_incomplete
                            — checkModel PASS but simulate FAIL
    behavioral_fixed        — checkModel PASS AND simulate PASS

  A root cause starts at NOT_ATTEMPTED.
  It becomes ATTEMPTED_INCOMPLETE when LLM touches it but structurally wrong.
  It becomes STRUCTURAL_FIXED when checkModel passes (structurally correct).
  It becomes BEHAVIORAL_FIXED when simulate also passes (fully correct).

This module is shared by the runner (for inline attribution) and the analyzer
(for offline audit).
"""
from __future__ import annotations

import re


# ── state constants ──────────────────────────────────────────────────────────

NOT_ATTEMPTED                      = "not_attempted"
ATTEMPTED_INCOMPLETE               = "attempted_incomplete"
STRUCTURAL_FIXED                   = "structural_fixed"
STRUCTURAL_FIXED_BEHAVIORAL_INCOMPLETE = "structural_fixed_behavioral_incomplete"
BEHAVIORAL_FIXED                  = "behavioral_fixed"


# ── PP (parameter_promotion) state detection ─────────────────────────────────

def _extract_pp_source_value(source_text: str, pp_target: str) -> str | None:
    param_re = re.compile(
        rf'^\s*parameter\s+Real\s{re.escape(pp_target)}\b[^=]*=\s*([^;\s]+)',
        re.MULTILINE,
    )
    m = param_re.search(source_text)
    if m:
        return m.group(1).strip()
    return None


def _pp_state(
    text: str,
    pp_target: str,
    source_text: str | None = None,
    check_ok: bool = False,
    simulate_ok: bool = False,
) -> str:
    """Return five-valued state for a parameter_promotion root cause.

    check_ok/simulate_ok refer to the WHOLE model, not just this variable.
    """
    # BEHAVIORAL_FIXED: parameter declaration restored AND simulate PASS
    param_pat = re.compile(
        rf'^\s*parameter\s+Real\s{re.escape(pp_target)}\b[^=]*=',
        re.MULTILINE,
    )
    if param_pat.search(text):
        if check_ok:
            return BEHAVIORAL_FIXED if simulate_ok else STRUCTURAL_FIXED_BEHAVIORAL_INCOMPLETE
        return ATTEMPTED_INCOMPLETE

    # STRUCTURAL_FIXED: defining equation present AND checkModel PASS
    eq_pat = re.compile(
        rf'^\s*{re.escape(pp_target)}\s*=\s*([^;\n]+)',
        re.MULTILINE,
    )
    m = eq_pat.search(text)
    if m:
        if check_ok:
            return BEHAVIORAL_FIXED if simulate_ok else STRUCTURAL_FIXED_BEHAVIORAL_INCOMPLETE
        return ATTEMPTED_INCOMPLETE

    # ATTEMPTED_INCOMPLETE: declared as Real with a value
    real_with_val = re.compile(
        rf'^\s*Real\s{re.escape(pp_target)}\b[^\n=]*=',
        re.MULTILINE,
    )
    if real_with_val.search(text):
        return ATTEMPTED_INCOMPLETE

    return NOT_ATTEMPTED


# ── PV (phantom_variable) state detection ────────────────────────────────────

def _pv_state(
    text: str,
    pv_target: str,
    pv_base_var: str,
    check_ok: bool = False,
    simulate_ok: bool = False,
) -> str:
    """Return five-valued state for a phantom_variable root cause.

    check_ok/simulate_ok refer to the WHOLE MODEL.
    """
    decl_re = re.compile(rf'^\s*Real\s{re.escape(pv_target)}\b', re.MULTILINE)
    target_tokens = len(re.findall(rf'\b{re.escape(pv_target)}\b', text))
    base_present = re.search(rf'\b{re.escape(pv_base_var)}\b', text) is not None

    # Fully resolved
    if (not decl_re.search(text)) and target_tokens == 0 and base_present:
        if check_ok:
            return BEHAVIORAL_FIXED if simulate_ok else STRUCTURAL_FIXED_BEHAVIORAL_INCOMPLETE
        return ATTEMPTED_INCOMPLETE

    # Bridge equation
    bridge_pat = re.compile(
        rf'^\s*{re.escape(pv_target)}\s*=\s*{re.escape(pv_base_var)}\s*;',
        re.MULTILINE,
    )
    if bridge_pat.search(text):
        return ATTEMPTED_INCOMPLETE

    # Commented declaration
    commented_decl = re.compile(
        rf'^\s*//\s*Real\s{re.escape(pv_target)}\b',
        re.MULTILINE,
    )
    if commented_decl.search(text):
        return ATTEMPTED_INCOMPLETE

    # Phantom has a defining equation
    phantom_eq = re.compile(
        rf'^\s*{re.escape(pv_target)}\s*=',
        re.MULTILINE,
    )
    if decl_re.search(text) and phantom_eq.search(text):
        return ATTEMPTED_INCOMPLETE

    return NOT_ATTEMPTED


# ── pattern builders ─────────────────────────────────────────────────────────

def _structural_fixed_states() -> frozenset:
    return frozenset({STRUCTURAL_FIXED, STRUCTURAL_FIXED_BEHAVIORAL_INCOMPLETE, BEHAVIORAL_FIXED})


def _structural_fix_pattern(states: list[str]) -> str:
    labels = []
    sf = _structural_fixed_states()
    if len(states) >= 1 and states[0] in sf:
        labels.append("pp1")
    if len(states) >= 2 and states[1] in sf:
        labels.append("pp2")
    if len(states) >= 3 and states[2] in sf:
        labels.append("pv")
    return "_".join(labels) if labels else "none"


def _behavioral_fix_pattern(states: list[str]) -> str:
    labels = []
    if len(states) >= 1 and states[0] == BEHAVIORAL_FIXED:
        labels.append("pp1")
    if len(states) >= 2 and states[1] == BEHAVIORAL_FIXED:
        labels.append("pp2")
    if len(states) >= 3 and states[2] == BEHAVIORAL_FIXED:
        labels.append("pv")
    return "_".join(labels) if labels else "none"


def _attempt_pattern(states: list[str]) -> str:
    labels = []
    sf = _structural_fixed_states()
    for i, s in enumerate(states[:3]):
        if s in sf or s == ATTEMPTED_INCOMPLETE:
            labels.append(["pp1", "pp2", "pv"][i])
    return "_".join(labels) if labels else "none"


def _new_structural_fix_pattern(prev_states: list[str], now_states: list[str]) -> str:
    sf = _structural_fixed_states()
    labels = []
    for i, (prev, now) in enumerate(zip(prev_states, now_states)):
        if now in sf and prev not in sf:
            labels.append(["pp1", "pp2", "pv"][i])
    return "_".join(labels) if labels else "none"


def _new_behavioral_fix_pattern(prev_states: list[str], now_states: list[str]) -> str:
    labels = []
    for i, (prev, now) in enumerate(zip(prev_states, now_states)):
        if now == BEHAVIORAL_FIXED and prev != BEHAVIORAL_FIXED:
            labels.append(["pp1", "pp2", "pv"][i])
    return "_".join(labels) if labels else "none"


def _new_attempt_pattern(prev_states: list[str], now_states: list[str]) -> str:
    sf = _structural_fixed_states()
    labels = []
    for i, (prev, now) in enumerate(zip(prev_states, now_states)):
        if now in sf and prev == NOT_ATTEMPTED:
            labels.append(["pp1", "pp2", "pv"][i])
        elif now == ATTEMPTED_INCOMPLETE and prev == NOT_ATTEMPTED:
            labels.append(["pp1", "pp2", "pv"][i])
    return "_".join(labels) if labels else "none"


def _reverted_pattern(prev_states: list[str], now_states: list[str]) -> str:
    sf = _structural_fixed_states()
    labels = []
    for i, (prev, now) in enumerate(zip(prev_states, now_states)):
        if prev in sf and now not in sf:
            labels.append(["pp1", "pp2", "pv"][i])
    return "_".join(labels) if labels else "none"


# ── convenience: compute all states for a single model text ──────────────────

def compute_states(
    text: str,
    pp1_target: str,
    pp2_target: str,
    pv_target: str,
    pv_base_var: str,
    source_text: str | None = None,
    check_ok: bool = False,
    simulate_ok: bool = False,
) -> dict[str, str]:
    """Return a dict with all three root-cause states for a model text.

    Pass check_ok/simulate_ok=True when the OMC returned PASS for the whole model.
    """
    return {
        "pp1": _pp_state(text, pp1_target, source_text, check_ok, simulate_ok),
        "pp2": _pp_state(text, pp2_target, source_text, check_ok, simulate_ok),
        "pv":  _pv_state(text, pv_target, pv_base_var, check_ok, simulate_ok),
    }
