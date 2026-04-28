from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scripts.diagnostic_context_dm_v0_19_35 import (
    _Equation,
    _dm_underdetermined_component,
    _extract_var_tokens,
    _maximum_matching,
    _parse_algebraic_variables,
    _parse_equations,
    _var_descriptions,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "structural_tools_v0_28_1"

_STRUCTURAL_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "who_defines",
        "description": (
            "Find equations where the given variable appears on the left-hand side (LHS). "
            "Returns equation texts that define this variable."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {"type": "string", "description": "Modelica model source code (omit to use current model)."},
                "var_name": {"type": "string", "description": "Variable name to search for on LHS."},
            },
            "required": ["var_name"],
        },
    },
    {
        "name": "who_uses",
        "description": (
            "Find equations where the given variable appears on the right-hand side (RHS). "
            "Returns equation texts that reference this variable."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {"type": "string", "description": "Modelica model source code (omit to use current model)."},
                "var_name": {"type": "string", "description": "Variable name to search for in equation references."},
            },
            "required": ["var_name"],
        },
    },
    {
        "name": "declared_but_unused",
        "description": (
            "Find Real variables that are declared but do not appear in ANY equation. "
            "These are likely phantom variables that should be removed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {"type": "string", "description": "Modelica model source code (omit to use current model)."},
            },
            "required": [],
        },
    },
    {
        "name": "get_unmatched_vars",
        "description": (
            "Run Dulmage-Mendelsohn bipartite graph decomposition to find root-cause variables "
            "that have no defining equation. Also returns the affected underdetermined subgraph. "
            "This is the most powerful structural diagnostic tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {"type": "string", "description": "Modelica model source code (omit to use current model)."},
            },
            "required": [],
        },
    },
    {
        "name": "causalized_form",
        "description": (
            "Modelica equations are acausal — they have NO direction (a=b and b=a are the same thing). "
            "This is unlike normal programming where every statement assigns a result to a variable. "
            "This tool converts equations into causal assignment form using ':=' notation, "
            "showing which variable OMC would compute from each equation. "
            "The output looks like familiar code: 'x := y + z' instead of 'x = y + z'. "
            "Use this when you find the equation system confusing or can't tell which variable "
            "depends on which — it reveals the hidden dependency structure."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {"type": "string", "description": "Modelica model source code (omit to use current model)."},
            },
            "required": [],
        },
    },
]


def who_defines(model_text: str, var_name: str) -> str:
    eq_match = re.search(r"^equation\s*$", model_text, re.MULTILINE)
    if not eq_match:
        return json.dumps({"error": "no equation section found", "var_name": var_name, "equations": []})
    decl_text = model_text[: eq_match.start()]
    variables = _parse_algebraic_variables(decl_text)
    known_vars = set(variables)
    equations = _parse_equations(model_text, known_vars)
    matching = [eq.text for eq in equations if eq.lhs_var == var_name]
    return json.dumps({"var_name": var_name, "equations": matching, "count": len(matching)})


def who_uses(model_text: str, var_name: str) -> str:
    eq_match = re.search(r"^equation\s*$", model_text, re.MULTILINE)
    if not eq_match:
        return json.dumps({"error": "no equation section found", "var_name": var_name, "equations": []})
    decl_text = model_text[: eq_match.start()]
    variables = _parse_algebraic_variables(decl_text)
    known_vars = set(variables)
    equations = _parse_equations(model_text, known_vars)
    using = [eq.text for eq in equations if var_name in eq.all_vars and eq.lhs_var != var_name]
    return json.dumps({"var_name": var_name, "equations": using, "count": len(using)})


def declared_but_unused(model_text: str) -> str:
    eq_match = re.search(r"^equation\s*$", model_text, re.MULTILINE)
    if not eq_match:
        return json.dumps({"error": "no equation section found", "unused_vars": []})
    decl_text = model_text[: eq_match.start()]
    variables = _parse_algebraic_variables(decl_text)
    known_vars = set(variables)
    equations = _parse_equations(model_text, known_vars)
    all_mentioned: set[str] = set()
    for eq in equations:
        all_mentioned |= eq.all_vars
    unused = sorted(v for v in variables if v not in all_mentioned)
    hints = []
    for v in unused:
        if v.endswith("_phantom"):
            base = v[: -len("_phantom")]
            hints.append(f"{v}: phantom variable — remove declaration and restore {base} references in equations")
        else:
            hints.append(f"{v}: no equation references this variable — may need a defining equation")
    return json.dumps({"unused_vars": unused, "count": len(unused), "hints": hints})


def get_unmatched_vars(model_text: str) -> str:
    eq_match = re.search(r"^equation\s*$", model_text, re.MULTILINE)
    if not eq_match:
        return "No equation section found in model."
    decl_text = model_text[: eq_match.start()]
    variables = _parse_algebraic_variables(decl_text)
    if not variables:
        return "No algebraic variables found."
    known_vars = set(variables)
    equations = _parse_equations(model_text, known_vars)
    eq_by_index = {eq.index: eq for eq in equations}
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
    lines: list[str] = ["STRUCTURAL DIAGNOSTIC (Dulmage-Mendelsohn)", ""]
    lines.append(f"Root cause variable(s) (no defining equation): {', '.join(root_cause)}")
    for v in root_cause:
        desc = descs.get(v, "")
        tag = f' "{desc}"' if desc else ""
        if v.endswith("_phantom"):
            base = v[: -len("_phantom")]
            lines.append(f"  {v}{tag}: phantom — remove declaration, replace with {base}")
        else:
            lines.append(f"  {v}{tag}: add defining equation or restore as parameter")
    non_root = [v for v in subgraph_vars if v not in root_cause]
    if non_root:
        lines.append("")
        lines.append(f"Connected variables affected: {', '.join(non_root)}")
    if subgraph_eqs:
        lines.append("")
        lines.append("Equations in underdetermined subgraph:")
        for eq in subgraph_eqs[:8]:
            lines.append(f"  {eq.text}")
        if len(subgraph_eqs) > 8:
            lines.append(f"  ... ({len(subgraph_eqs) - 8} more)")
    return "\n".join(lines)


def causalized_form(model_text: str) -> str:
    eq_match = re.search(r"^equation\s*$", model_text, re.MULTILINE)
    if not eq_match:
        return "No equation section found."
    decl_text = model_text[: eq_match.start()]
    variables = _parse_algebraic_variables(decl_text)
    known_vars = set(variables)
    equations = _parse_equations(model_text, known_vars)

    lines: list[str] = ["CAUSALIZED EQUATION FORM", ""]
    lines.append("OMC internally assigns a causal direction to each acausal equation.")
    lines.append("Below is the equation section with each equation's likely solve target.")
    lines.append("Equations with ':=' show the variable OMC would compute from that equation.")
    lines.append("")

    for eq in equations:
        lhs = eq.lhs_var
        text = eq.text
        if lhs and lhs in known_vars:
            # Rewrite as causal assignment: strip original LHS, show as var := rest
            eq_body = text
            # Find the first '=' and replace what's on the left with just the var
            parts = text.split("=", 1)
            if len(parts) == 2:
                rhs = parts[1].strip().rstrip(";")
                causal = f"  {lhs} := {rhs};"
            else:
                causal = f"  // Causal target: {lhs} — {text}"
        else:
            causal = f"  // No clear causal target — {text}"
        lines.append(causal)

    lines.append("")
    lines.append("NOTE: ':=' notation shows the CAUSAL DIRECTION OMC would assign.")
    lines.append("The original equations remain acausal (reversible) in the actual model.")
    return "\n".join(lines)


def get_structural_tool_defs() -> list[dict[str, Any]]:
    return list(_STRUCTURAL_TOOL_DEFS)


def dispatch_structural_tool(name: str, arguments: dict) -> str:
    model_text = str(arguments.get("model_text") or "")
    if not model_text.strip():
        return json.dumps({"error": "empty_model_text"})
    if name == "who_defines":
        return who_defines(model_text, str(arguments.get("var_name") or ""))
    if name == "who_uses":
        return who_uses(model_text, str(arguments.get("var_name") or ""))
    if name == "declared_but_unused":
        return declared_but_unused(model_text)
    if name == "get_unmatched_vars":
        return get_unmatched_vars(model_text)
    if name == "causalized_form":
        return causalized_form(model_text)
    return json.dumps({"error": f"unknown_structural_tool:{name}"})
