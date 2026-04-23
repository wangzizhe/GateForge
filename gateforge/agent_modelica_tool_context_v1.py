"""Modelica query-tool observation context for repair prompts (v0.19.54).

This module converts v0.19.53 query API facts into a compact observation block
that can be passed to an LLM. It is deliberately non-prescriptive: no repair
actions, no root-cause labels, no patch generation.
"""
from __future__ import annotations

from typing import Any

from .agent_modelica_omc_query_api_v1 import (
    extract_real_declarations,
    structural_signal_summary,
    who_defines,
    who_uses,
)
from .omc_diagnostic_formatter_v0_19_48 import _extract_undersolved_variables


def extract_omc_no_equation_variables(omc_output: str) -> list[str]:
    """Return variable names explicitly reported by OMC as lacking equations."""
    names: list[str] = []
    seen: set[str] = set()
    for item in _extract_undersolved_variables(str(omc_output or "")):
        if item.name and item.name not in seen:
            seen.add(item.name)
            names.append(item.name)
    return names


def _compact_statement_rows(rows: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for row in rows[:limit]:
        text = " ".join(str(row.get("statement_text") or "").split())
        compact.append(
            {
                "line_start": row.get("line_start"),
                "line_end": row.get("line_end"),
                "lhs": row.get("lhs"),
                "is_connect": bool(row.get("is_connect")),
                "statement": text[:240],
            }
        )
    return compact


def _declaration_facts(model_text: str) -> dict[str, dict[str, Any]]:
    facts: dict[str, dict[str, Any]] = {}
    for decl in extract_real_declarations(model_text):
        facts[str(decl["name"])] = {
            "name": decl["name"],
            "kind": decl["kind"],
            "line": decl["line"],
            "section": decl["section"],
            "has_binding": bool(decl["has_binding"]),
        }
    return facts


def build_modelica_query_tool_context(
    *,
    model_text: str,
    omc_output: str,
    max_variables: int = 8,
) -> dict[str, Any]:
    """Build structural tool observations for the current repair state.

    The returned object contains facts only:
    - OMC no-equation variable names
    - text-query structural summary
    - declaration, definition, and use sites for selected variables

    It intentionally does not label root causes or propose edits.
    """
    summary = structural_signal_summary(model_text)
    declarations = _declaration_facts(model_text)
    omc_no_equation = extract_omc_no_equation_variables(omc_output)

    selected: list[str] = []
    seen: set[str] = set()

    def add_names(names: list[str]) -> None:
        for name in names:
            if not name or name in seen:
                continue
            seen.add(name)
            selected.append(name)

    add_names(omc_no_equation)
    add_names([row["name"] for row in summary["variables_with_no_defining_equation"]])
    add_names([row["name"] for row in summary["unbound_parameters"]])
    add_names([row["name"] for row in summary["declared_but_unused"]])
    add_names([row["name"] for row in summary["used_but_undeclared"]])

    selected = selected[:max_variables]
    variable_facts = []
    for name in selected:
        variable_facts.append(
            {
                "name": name,
                "declaration": declarations.get(name),
                "definitions": _compact_statement_rows(who_defines(model_text, name)),
                "uses": _compact_statement_rows(who_uses(model_text, name)),
            }
        )

    return {
        "schema_version": "gateforge_modelica_query_tool_context_v1",
        "source": "v0.19.53_query_api_plus_omc_diagnostic_parser",
        "limitations": [
            "text parser only; inherited declarations and equations are not flattened",
            "connect statements are recorded but not expanded into implicit equations",
            "arrays, branches, loops, and algorithm sections may be partial",
        ],
        "omc_no_equation_variables": omc_no_equation,
        "summary": {
            "declaration_count": summary["declaration_count"],
            "equation_count": summary["equation_count"],
            "connect_count": summary["connect_count"],
            "variables_with_no_defining_equation": [
                row["name"] for row in summary["variables_with_no_defining_equation"]
            ],
            "unbound_parameters": [
                row["name"] for row in summary["unbound_parameters"]
            ],
            "declared_but_unused": [
                row["name"] for row in summary["declared_but_unused"]
            ],
            "used_but_undeclared": [
                row["name"] for row in summary["used_but_undeclared"]
            ],
        },
        "selected_variables": selected,
        "variable_facts": variable_facts,
    }


def format_modelica_query_tool_context(context: dict[str, Any]) -> str:
    """Format query-tool observations as a compact prompt block."""
    if not context:
        return ""
    summary = context.get("summary") or {}
    lines = [
        "=== modelica_query_tool_observations ===",
        f"schema_version: {context.get('schema_version', '')}",
        "limitations:",
    ]
    for item in context.get("limitations") or []:
        lines.append(f"- {item}")

    lines.append("summary:")
    lines.append(f"- declaration_count: {summary.get('declaration_count', 0)}")
    lines.append(f"- equation_count: {summary.get('equation_count', 0)}")
    lines.append(f"- connect_count: {summary.get('connect_count', 0)}")
    lines.append(
        "- omc_no_equation_variables: "
        + ", ".join(context.get("omc_no_equation_variables") or [])
    )
    lines.append(
        "- variables_with_no_defining_equation: "
        + ", ".join(summary.get("variables_with_no_defining_equation") or [])
    )
    lines.append(
        "- unbound_parameters: "
        + ", ".join(summary.get("unbound_parameters") or [])
    )
    lines.append(
        "- declared_but_unused: "
        + ", ".join(summary.get("declared_but_unused") or [])
    )
    lines.append(
        "- used_but_undeclared: "
        + ", ".join(summary.get("used_but_undeclared") or [])
    )

    lines.append("selected_variable_facts:")
    for item in context.get("variable_facts") or []:
        declaration = item.get("declaration")
        if declaration:
            decl_text = (
                f"{declaration.get('kind')} line {declaration.get('line')} "
                f"section={declaration.get('section')} "
                f"has_binding={declaration.get('has_binding')}"
            )
        else:
            decl_text = "not found by text declaration parser"
        lines.append(f"- variable: {item.get('name')}")
        lines.append(f"  declaration: {decl_text}")
        lines.append("  definitions:")
        for row in item.get("definitions") or []:
            lines.append(
                f"    line {row.get('line_start')}: "
                f"{row.get('statement', '')}"
            )
        if not item.get("definitions"):
            lines.append("    (none found by query parser)")
        lines.append("  uses:")
        for row in item.get("uses") or []:
            lines.append(
                f"    line {row.get('line_start')}: "
                f"{row.get('statement', '')}"
            )
        if not item.get("uses"):
            lines.append("    (none found by query parser)")
    lines.append("=== end_modelica_query_tool_observations ===")
    return "\n".join(lines)

