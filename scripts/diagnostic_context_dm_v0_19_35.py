"""DM-based diagnostic context extraction for underdetermined Modelica models.

Uses Dulmage-Mendelsohn (bipartite graph) decomposition to identify root cause
variables (those with no defining equation) rather than just symptom variables
reported by OMC.

Applicable to flat Modelica models (no component hierarchy).
Does not require OMC — pure static analysis of model source text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── Modelica keywords / builtins to ignore during tokenization ────────────────

_KEYWORDS = frozenset({
    'der', 'if', 'then', 'else', 'elseif', 'end', 'equation', 'model',
    'Real', 'Integer', 'Boolean', 'String', 'parameter', 'constant',
    'discrete', 'input', 'output', 'flow', 'stream', 'time',
    'true', 'false', 'and', 'or', 'not', 'connect', 'annotation',
    'import', 'package', 'class', 'record', 'block', 'type', 'extends',
    'abs', 'sign', 'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2',
    'exp', 'log', 'log10', 'sqrt', 'max', 'min', 'mod', 'rem',
    'ceil', 'floor', 'integer', 'noEvent', 'smooth', 'sample',
    'pre', 'edge', 'change', 'reinit', 'terminal', 'initial',
    'algorithm', 'when', 'elsewhen', 'assert', 'terminate',
    'homotopy', 'semiLinear', 'inStream', 'actualStream',
})

_TOKEN_RE = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\b')


# ── data structures ───────────────────────────────────────────────────────────

@dataclass
class _Equation:
    index: int
    text: str
    lhs_var: str               # variable this equation primarily defines
    all_vars: frozenset[str]   # all variable references in equation text


# ── model parsing ─────────────────────────────────────────────────────────────

def _parse_algebraic_variables(decl_text: str) -> list[str]:
    """Return names of algebraic Real variables (not parameter/constant)."""
    results = []
    for line in decl_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('//'):
            continue
        # Skip parameter / constant declarations
        if re.match(r'^(?:parameter|constant|discrete)\s+', stripped):
            continue
        # Match plain Real declaration
        m = re.match(
            r'^Real\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s*\([^)]*\))?'
            r'(?:\s*=[^;"]*)?\s*(?:"[^"]*")?\s*;',
            stripped,
        )
        if m:
            results.append(m.group(1))
    return results


def _extract_var_tokens(text: str, known_vars: set[str]) -> frozenset[str]:
    """Extract variable tokens from equation text, filtering keywords."""
    return frozenset(
        m.group(1) for m in _TOKEN_RE.finditer(text)
        if m.group(1) not in _KEYWORDS and m.group(1) in known_vars
    )


def _parse_equations(eq_text: str, known_vars: set[str]) -> list[_Equation]:
    """Parse equation section; return list of _Equation objects."""
    lines = eq_text.splitlines()
    equations: list[_Equation] = []
    eq_idx = 0
    in_eq = False
    i = 0

    while i < len(lines):
        s = lines[i].strip()
        if re.match(r'^equation\s*$', s):
            in_eq = True
            i += 1
            continue
        if re.match(r'^(algorithm|initial\s+equation|end\s+)', s):
            in_eq = False
            i += 1
            continue
        if not in_eq or not s or s.startswith('//'):
            i += 1
            continue
        if s.startswith('connect(') or s.startswith('annotation'):
            while i < len(lines) and ';' not in lines[i]:
                i += 1
            i += 1
            continue
        if '=' not in s:
            i += 1
            continue

        parts = [lines[i]]
        while ';' not in lines[i] and i + 1 < len(lines):
            i += 1
            parts.append(lines[i])
        stmt = ' '.join(p.strip() for p in parts)

        lhs_raw = stmt.split('=')[0].strip().lstrip('-').strip()
        if lhs_raw.startswith('der('):
            m = re.match(r'der\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)', lhs_raw)
            lhs_var = m.group(1) if m else ''
        else:
            m = re.match(r'([A-Za-z_][A-Za-z0-9_]*)', lhs_raw)
            lhs_var = m.group(1) if m else ''

        equations.append(_Equation(
            index=eq_idx,
            text=stmt.strip(),
            lhs_var=lhs_var,
            all_vars=_extract_var_tokens(stmt, known_vars),
        ))
        eq_idx += 1
        i += 1

    return equations


def _var_descriptions(model_text: str, var_names: set[str]) -> dict[str, str]:
    """Return description string for each requested variable name."""
    desc_re = re.compile(
        r'^\s*(?:parameter\s+|constant\s+)?Real\s+([A-Za-z_][A-Za-z0-9_]*)'
        r'[^"\n]*"([^"]*)"',
        re.MULTILINE,
    )
    return {
        m.group(1): m.group(2)
        for m in desc_re.finditer(model_text)
        if m.group(1) in var_names
    }


# ── bipartite maximum matching (LHS-preferring augmenting path) ───────────────

def _maximum_matching(
    variables: list[str],
    equations: list[_Equation],
    var_to_eqs: dict[str, list[int]],
) -> dict[str, int]:
    """Maximum bipartite matching with LHS-variable preference.

    Phase 1: greedily match each equation to its declared LHS variable.
             This ensures `x = rhs` and `der(x) = rhs` equations stay
             anchored to their natural variable, so the matching reflects
             the model's intended causal structure.
    Phase 2: augmenting-path search for any remaining unmatched variables.

    Returns var → eq_index mapping.
    """
    var_match: dict[str, int] = {}
    eq_match: dict[int, str] = {}

    # Phase 1: LHS preference
    for eq in equations:
        lhs = eq.lhs_var
        if lhs and lhs in var_to_eqs and lhs not in var_match and eq.index not in eq_match:
            var_match[lhs] = eq.index
            eq_match[eq.index] = lhs

    # Phase 2: augmenting path for remaining unmatched variables
    def _augment(var: str, visited: set[int]) -> bool:
        for eq_idx in var_to_eqs.get(var, []):
            if eq_idx in visited:
                continue
            visited.add(eq_idx)
            if eq_idx not in eq_match or _augment(eq_match[eq_idx], visited):
                var_match[var] = eq_idx
                eq_match[eq_idx] = var
                return True
        return False

    for var in variables:
        if var not in var_match:
            _augment(var, set())

    return var_match


# ── DM underdetermined component ──────────────────────────────────────────────

def _dm_underdetermined_component(
    variables: list[str],
    eq_by_index: dict[int, _Equation],
    var_to_eqs: dict[str, list[int]],
    matching: dict[str, int],
) -> tuple[list[str], list[str], list[_Equation]]:
    """Return (root_cause_vars, subgraph_vars, subgraph_eqs).

    root_cause_vars: unmatched variables (no defining equation)
    subgraph_vars:   all variables reachable via alternating BFS from root causes
    subgraph_eqs:    equations in the underdetermined component
    """
    eq_to_var: dict[int, str] = {v: k for k, v in matching.items()}
    matched_set = set(matching.keys())
    unmatched = [v for v in variables if v not in matched_set]

    if not unmatched:
        return [], [], []

    # Alternating BFS: unmatched_var → equations (unmatched edges)
    #                  → matched variable of equation (matched edge) → ...
    visited_vars: set[str] = set(unmatched)
    visited_eqs: set[int] = set()
    queue = list(unmatched)

    while queue:
        var = queue.pop()
        for eq_idx in var_to_eqs.get(var, []):
            if eq_idx in visited_eqs:
                continue
            visited_eqs.add(eq_idx)
            if eq_idx in eq_to_var:
                matched_var = eq_to_var[eq_idx]
                if matched_var not in visited_vars:
                    visited_vars.add(matched_var)
                    queue.append(matched_var)

    subgraph_vars = list(visited_vars)
    subgraph_eqs = [eq_by_index[i] for i in visited_eqs if i in eq_by_index]
    return unmatched, subgraph_vars, subgraph_eqs


# ── public API ────────────────────────────────────────────────────────────────

def build_dm_diagnostic_context(model_text: str) -> str:
    """Build DM-based diagnostic context string from a flat Modelica model.

    Returns a compact string (target < 600 chars) naming the root cause
    variable(s) and the underdetermined equation subgraph.
    Falls back to a brief error message if analysis finds nothing.
    """
    eq_match = re.search(r'^equation\s*$', model_text, re.MULTILINE)
    if not eq_match:
        return "Structural error: no equation section found in model."

    decl_text = model_text[: eq_match.start()]
    variables = _parse_algebraic_variables(decl_text)
    if not variables:
        return "Structural error: no algebraic variables found."

    known_vars = set(variables)
    equations = _parse_equations(model_text, known_vars)
    eq_by_index = {eq.index: eq for eq in equations}

    # Build var → [eq_index] incidence
    var_to_eqs: dict[str, list[int]] = {v: [] for v in variables}
    for eq in equations:
        for var in eq.all_vars:
            if var in var_to_eqs:
                var_to_eqs[var].append(eq.index)

    matching = _maximum_matching(variables, equations, var_to_eqs)
    root_cause, subgraph_vars, subgraph_eqs = _dm_underdetermined_component(
        variables, eq_by_index, var_to_eqs, matching
    )

    if not root_cause:
        return "DM analysis: no underdetermined variables found."

    descs = _var_descriptions(model_text, set(root_cause + subgraph_vars))

    lines: list[str] = ["STRUCTURAL DIAGNOSTIC (Dulmage-Mendelsohn)"]
    lines.append("")

    # Root cause variables
    if len(root_cause) == 1:
        v = root_cause[0]
        desc = descs.get(v, "")
        tag = f'  "{desc}"' if desc else ""
        lines.append(f"Root cause variable (no defining equation): {v}{tag}")
        lines.append("  Fix: add a defining equation (e.g., var = value;), or remove this variable and restore the original reference.")
    else:
        lines.append(f"Root cause variables (no defining equation): {', '.join(root_cause)}")
        for v in root_cause:
            desc = descs.get(v, "")
            if desc:
                lines.append(f'  {v}: "{desc}"')

    non_root = [v for v in subgraph_vars if v not in root_cause]
    if non_root:
        lines.append("")
        lines.append(f"Connected variables affected: {', '.join(non_root)}")

    if subgraph_eqs:
        lines.append("")
        lines.append("Equations in underdetermined subgraph:")
        for eq in subgraph_eqs[:6]:
            lines.append(f"  {eq.text}")
        if len(subgraph_eqs) > 6:
            lines.append(f"  ... ({len(subgraph_eqs) - 6} more)")

    return "\n".join(lines)
