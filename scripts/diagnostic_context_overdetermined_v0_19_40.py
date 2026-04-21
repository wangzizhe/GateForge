"""Overdetermined diagnostic context for flat Modelica models (v0.19.40).

Identifies over-constrained variables: algebraic variables that have more
than one defining equation.  OMC only reports the equation/variable count
imbalance; it does not name which variable has the conflicting equations.
This module fills that gap by static analysis.

Strategy:
  1. Parse all algebraic variables (non-parameter, non-state).
  2. For each equation, determine its LHS variable.
  3. Find variables with >1 defining equation.
  4. Report conflicting equations and suggest removing the redundant one.
"""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\b')
_KEYWORDS = frozenset({
    'der', 'if', 'then', 'else', 'elseif', 'end', 'equation', 'model',
    'Real', 'Integer', 'Boolean', 'String', 'parameter', 'constant',
    'discrete', 'input', 'output', 'flow', 'stream', 'time',
    'true', 'false', 'and', 'or', 'not', 'connect', 'annotation',
    'import', 'package', 'class', 'record', 'block', 'type', 'extends',
    'abs', 'sign', 'sin', 'cos', 'tan', 'exp', 'log', 'sqrt',
    'max', 'min', 'mod', 'rem', 'ceil', 'floor',
    'algorithm', 'when', 'elsewhen', 'assert',
})


def _parse_alg_var_descriptions(model_text: str) -> dict[str, str]:
    """Return {var_name: description} for all algebraic Real variables."""
    desc_re = re.compile(
        r'^\s*Real\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s*\([^)]*\))?\s*"([^"]*)"',
        re.MULTILINE,
    )
    result = {}
    for m in desc_re.finditer(model_text):
        result[m.group(1)] = m.group(2)
    return result


def _parse_defining_equations(model_text: str) -> dict[str, list[str]]:
    """Return {var_name: [eq_text, ...]} for equations that define a variable.

    A "defining equation" is one whose LHS is `var` or `der(var)`.
    Only algebraic (non-der) equations are tracked for overdetermined detection.
    """
    eq_match = re.search(r'^equation\s*$', model_text, re.MULTILINE)
    if not eq_match:
        return {}

    lines = model_text[eq_match.start():].splitlines()
    defining: dict[str, list[str]] = {}
    in_eq = False
    i = 0

    while i < len(lines):
        s = lines[i].strip()
        if re.match(r'^equation\s*$', s):
            in_eq = True; i += 1; continue
        if re.match(r'^(algorithm|initial\s+equation|end\s+)', s):
            in_eq = False; i += 1; continue
        if not in_eq or not s or s.startswith('//'):
            i += 1; continue
        if s.startswith('connect(') or s.startswith('annotation'):
            while i < len(lines) and ';' not in lines[i]:
                i += 1
            i += 1; continue
        if '=' not in s:
            i += 1; continue

        parts = [lines[i]]
        while ';' not in lines[i] and i + 1 < len(lines):
            i += 1; parts.append(lines[i])
        stmt = ' '.join(p.strip() for p in parts)

        lhs_raw = stmt.split('=')[0].strip().lstrip('-').strip()
        # Skip derivative equations (they define state variables, not algebraic)
        if lhs_raw.startswith('der('):
            i += 1; continue

        m = re.match(r'([A-Za-z_][A-Za-z0-9_]*)', lhs_raw)
        if m:
            var = m.group(1)
            defining.setdefault(var, []).append(stmt.strip())
        i += 1

    return defining


def build_overdetermined_diagnostic_context(model_text: str) -> str:
    """Build diagnostic context for an overdetermined flat Modelica model.

    Returns a compact string naming the over-constrained variable(s) and
    their conflicting equations, with a per-variable fix hint.
    Falls back to a brief error message if analysis finds nothing.
    """
    defining = _parse_defining_equations(model_text)
    over_constrained = {v: eqs for v, eqs in defining.items() if len(eqs) > 1}

    if not over_constrained:
        return "Overdetermined analysis: no variable with multiple defining equations found."

    descs = _parse_alg_var_descriptions(model_text)

    lines: list[str] = ["STRUCTURAL DIAGNOSTIC (overdetermined)"]
    lines.append("")
    lines.append(
        f"Over-constrained variable(s) (more than one defining equation): "
        f"{', '.join(sorted(over_constrained))}"
    )

    for var in sorted(over_constrained):
        eqs = over_constrained[var]
        desc = descs.get(var, "")
        tag = f' "{desc}"' if desc else ""
        lines.append(f"")
        lines.append(f"  {var}:{tag}")
        lines.append(f"    Fix: Remove the redundant equation for {var}. Keep only one definition.")
        for idx, eq in enumerate(eqs):
            label = "  (original)" if idx == 0 else "  (redundant — remove this)"
            lines.append(f"    Eq {idx + 1}: {eq}{label}")

    return "\n".join(lines)
