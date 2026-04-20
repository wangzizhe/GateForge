"""Diagnostic context extraction for Modelica underdetermined structural errors.

Given a broken Modelica model and OMC error output, extracts:
  1. Which variable(s) are underdetermined (from OMC error text)
  2. Their physical descriptions (from variable declarations)
  3. Which equations reference them (from equation section)

Produces a structured context string that gives an LLM a more focused
starting point than the raw OMC error message alone.

No OMC dependency — pure text analysis.
"""
from __future__ import annotations

import re

# ── OMC error parsing ────────────────────────────────────────────────────────

_UNDET_VAR_RE = re.compile(
    r"Variable\s+([A-Za-z_][A-Za-z0-9_]*)\s+(?:is\s+)?not\s+determined",
    re.IGNORECASE,
)

# ── Modelica source parsing ──────────────────────────────────────────────────

# Matches: [parameter] Real varname [(opts)] [= value] "description" ;
_VAR_DECL_DESC_RE = re.compile(
    r"^\s*(?:parameter\s+)?Real\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\([^)]*\))?"
    r"(?:\s*=\s*[^\";\n]+)?"
    r'\s*"([^"]*)"',
    re.MULTILINE,
)


def _extract_underdetermined_variable_names(omc_error: str) -> list[str]:
    """Extract variable names from OMC 'not determined' error messages."""
    seen: dict[str, None] = {}
    for m in _UNDET_VAR_RE.finditer(omc_error):
        seen[m.group(1)] = None
    return list(seen)


def _find_variable_description(model_text: str, var_name: str) -> str:
    """Return the description string for a variable declaration, or ''."""
    for m in _VAR_DECL_DESC_RE.finditer(model_text):
        if m.group(1) == var_name:
            return m.group(2) or ""
    return ""


def _find_equations_referencing(model_text: str, var_name: str) -> list[str]:
    """Return equation texts from the equation section that reference var_name.

    Handles multi-line equations by accumulating until the closing semicolon.
    Skips connect() statements and comment-only lines.
    """
    lines = model_text.splitlines()
    token_re = re.compile(r"\b" + re.escape(var_name) + r"\b")
    results: list[str] = []
    in_eq = False
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if re.match(r"^equation\s*$", stripped):
            in_eq = True
            i += 1
            continue
        if re.match(r"^(algorithm|initial\s+equation|end\s+)", stripped):
            in_eq = False
            i += 1
            continue
        if not in_eq or not stripped or stripped.startswith("//"):
            i += 1
            continue
        if stripped.startswith("connect(") or stripped.startswith("annotation"):
            while i < len(lines) and ";" not in lines[i]:
                i += 1
            i += 1
            continue
        if "=" not in stripped:
            i += 1
            continue
        # Accumulate multi-line equation
        stmt_parts = [stripped]
        while ";" not in lines[i] and i + 1 < len(lines):
            i += 1
            stmt_parts.append(lines[i].strip())
        stmt_text = " ".join(stmt_parts)
        if token_re.search(stmt_text):
            results.append(stmt_text)
        i += 1
    return results


def build_diagnostic_context(broken_model_text: str, omc_error_text: str) -> str:
    """Build structured diagnostic context for LLM from broken model + OMC error.

    Returns a formatted string describing the underdetermined variable(s),
    their physical descriptions, and the equations referencing them.
    Falls back to a plain error block if no variable can be identified.
    """
    var_names = _extract_underdetermined_variable_names(omc_error_text)
    if not var_names:
        return (
            "Structural error: the model has more variables than equations.\n"
            f"OMC output:\n{omc_error_text.strip()}"
        )

    blocks: list[str] = []
    for var_name in var_names[:3]:
        description = _find_variable_description(broken_model_text, var_name)
        equations = _find_equations_referencing(broken_model_text, var_name)
        label = f'"{description}"' if description else "(no description found)"
        eq_lines = "\n".join(f"    {j + 1}. {eq}" for j, eq in enumerate(equations))
        block = (
            f"Underdetermined variable: {var_name}  {label}\n"
            f"  Equations referencing {var_name}:\n"
            + (eq_lines if equations else "    (none found in equation section)")
        )
        blocks.append(block)

    return (
        "STRUCTURAL DIAGNOSTIC\n"
        "The model checkModel failed because the following variable(s) have no "
        "defining equation:\n\n"
        + "\n\n".join(blocks)
        + f"\n\nOMC error:\n{omc_error_text.strip()}"
    )
