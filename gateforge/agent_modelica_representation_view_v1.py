"""Representation views for Modelica repair prompts (v0.19.56).

This module keeps the information source fixed and changes only the surface
representation presented to the LLM.
"""
from __future__ import annotations

import re
from typing import Any

from .agent_modelica_omc_query_api_v1 import (
    extract_equation_statements,
    extract_real_declarations,
    structural_signal_summary,
    who_defines,
    who_uses,
)
from .agent_modelica_tool_context_v1 import extract_omc_no_equation_variables


IDENT_RE = r"[A-Za-z_][A-Za-z0-9_]*"


def _find_reference_roots(text: str) -> set[str]:
    roots: set[str] = set()
    for match in re.finditer(rf"\b{IDENT_RE}\b", text or ""):
        start = match.start()
        if start > 0 and text[start - 1] == ".":
            continue
        roots.add(match.group(0))
    return roots


def _compact_equation_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _declaration_map(model_text: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for decl in extract_real_declarations(model_text):
        rows[str(decl["name"])] = {
            "name": decl["name"],
            "kind": decl["kind"],
            "line": decl["line"],
            "section": decl["section"],
            "has_binding": bool(decl["has_binding"]),
        }
    return rows


def build_causal_view(
    *,
    model_text: str,
    omc_output: str,
    max_variables: int = 8,
) -> dict[str, Any]:
    """Build a compact variable-centric causal view."""
    summary = structural_signal_summary(model_text)
    declarations = _declaration_map(model_text)
    undersolved = extract_omc_no_equation_variables(omc_output)

    selected: list[str] = []
    seen: set[str] = set()
    for bucket in (
        undersolved,
        [row["name"] for row in summary["variables_with_no_defining_equation"]],
        [row["name"] for row in summary["unbound_parameters"]],
        [row["name"] for row in summary["used_but_undeclared"]],
    ):
        for name in bucket:
            if name and name not in seen:
                seen.add(name)
                selected.append(name)
    selected = selected[:max_variables]

    variable_views = []
    for name in selected:
        defs = who_defines(model_text, name)
        uses = who_uses(model_text, name)
        variable_views.append(
            {
                "name": name,
                "declaration": declarations.get(name),
                "defined_by": [
                    {
                        "line_start": row.get("line_start"),
                        "equation": _compact_equation_text(row.get("statement_text")),
                    }
                    for row in defs[:4]
                ],
                "used_by": [
                    {
                        "line_start": row.get("line_start"),
                        "equation": _compact_equation_text(row.get("statement_text")),
                    }
                    for row in uses[:4]
                ],
            }
        )

    return {
        "schema_version": "gateforge_modelica_causal_view_v1",
        "undersolved_variables": undersolved,
        "selected_variables": selected,
        "unbound_parameters": [row["name"] for row in summary["unbound_parameters"]],
        "variable_views": variable_views,
    }


def format_causal_view(view: dict[str, Any]) -> str:
    """Format the causal view as a compact prompt block."""
    lines = [
        "=== modelica_causal_view ===",
        f"undersolved_variables: {', '.join(view.get('undersolved_variables') or [])}",
        f"selected_variables: {', '.join(view.get('selected_variables') or [])}",
        f"unbound_parameters: {', '.join(view.get('unbound_parameters') or [])}",
        "variable_causal_relations:",
    ]
    for item in view.get("variable_views") or []:
        decl = item.get("declaration")
        if decl:
            decl_text = (
                f"{decl.get('kind')} line {decl.get('line')} "
                f"section={decl.get('section')} has_binding={decl.get('has_binding')}"
            )
        else:
            decl_text = "not found by declaration parser"
        lines.append(f"- variable: {item.get('name')}")
        lines.append(f"  declaration: {decl_text}")
        lines.append("  defined_by:")
        for row in item.get("defined_by") or []:
            lines.append(f"    line {row.get('line_start')}: {row.get('equation')}")
        if not item.get("defined_by"):
            lines.append("    (none)")
        lines.append("  used_by:")
        for row in item.get("used_by") or []:
            lines.append(f"    line {row.get('line_start')}: {row.get('equation')}")
        if not item.get("used_by"):
            lines.append("    (none)")
    lines.append("=== end_modelica_causal_view ===")
    return "\n".join(lines)


def _tarjan_scc(graph: dict[int, set[int]]) -> list[list[int]]:
    index = 0
    stack: list[int] = []
    on_stack: set[int] = set()
    indices: dict[int, int] = {}
    lowlink: dict[int, int] = {}
    components: list[list[int]] = []

    def strongconnect(node: int) -> None:
        nonlocal index
        indices[node] = index
        lowlink[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for nxt in graph.get(node, set()):
            if nxt not in indices:
                strongconnect(nxt)
                lowlink[node] = min(lowlink[node], lowlink[nxt])
            elif nxt in on_stack:
                lowlink[node] = min(lowlink[node], indices[nxt])

        if lowlink[node] == indices[node]:
            component: list[int] = []
            while stack:
                cur = stack.pop()
                on_stack.remove(cur)
                component.append(cur)
                if cur == node:
                    break
            components.append(sorted(component))

    for node in sorted(graph):
        if node not in indices:
            strongconnect(node)
    return components


def build_blt_proxy_view(
    *,
    model_text: str,
    omc_output: str,
) -> dict[str, Any]:
    """Build a text-derived BLT-like block view for the current model."""
    statements = [
        stmt for stmt in extract_equation_statements(model_text)
        if not stmt.get("is_connect")
    ]
    eqs = []
    define_map: dict[str, set[int]] = {}
    for idx, stmt in enumerate(statements):
        defined_vars: set[str] = set()
        if stmt.get("lhs"):
            defined_vars.add(str(stmt["lhs"]))
        if stmt.get("base_variable"):
            defined_vars.add(str(stmt["base_variable"]))
        used_vars = {
            name for name in _find_reference_roots(str(stmt.get("rhs") or ""))
            if name not in {"der", "time", "sin", "cos", "sqrt", "exp", "log"}
        }
        eqs.append(
            {
                "eq_index": idx,
                "line_start": stmt.get("line_start"),
                "equation": _compact_equation_text(stmt.get("statement_text")),
                "defined_vars": sorted(defined_vars),
                "used_vars": sorted(used_vars),
            }
        )
        for name in defined_vars:
            define_map.setdefault(name, set()).add(idx)

    graph: dict[int, set[int]] = {idx: set() for idx in range(len(eqs))}
    for eq in eqs:
        for used in eq["used_vars"]:
            for src in define_map.get(used, set()):
                if src != eq["eq_index"]:
                    graph[src].add(eq["eq_index"])

    sccs = _tarjan_scc(graph)
    block_of_eq: dict[int, int] = {}
    for block_id, component in enumerate(sccs, start=1):
        for eq_index in component:
            block_of_eq[eq_index] = block_id

    blocks = []
    for block_id, component in enumerate(sccs, start=1):
        block_eqs = [eqs[i] for i in component]
        defined_vars = sorted({v for eq in block_eqs for v in eq["defined_vars"]})
        used_vars = sorted({v for eq in block_eqs for v in eq["used_vars"]})
        cross_block_uses = sorted(
            {
                used
                for eq in block_eqs
                for used in eq["used_vars"]
                if any(block_of_eq.get(src) != block_id for src in define_map.get(used, set()))
            }
        )
        blocks.append(
            {
                "block_id": block_id,
                "size": len(component),
                "equations": [
                    {
                        "line_start": eq["line_start"],
                        "equation": eq["equation"],
                    }
                    for eq in block_eqs
                ],
                "defined_vars": defined_vars,
                "used_vars": used_vars,
                "cross_block_uses": cross_block_uses,
            }
        )

    return {
        "schema_version": "gateforge_modelica_blt_proxy_view_v1",
        "undersolved_variables": extract_omc_no_equation_variables(omc_output),
        "block_count": len(blocks),
        "blocks": blocks,
    }


def format_blt_proxy_view(view: dict[str, Any]) -> str:
    """Format the BLT-like proxy view as a compact block list."""
    lines = [
        "=== modelica_blt_proxy_view ===",
        f"undersolved_variables: {', '.join(view.get('undersolved_variables') or [])}",
        f"block_count: {view.get('block_count', 0)}",
        "blocks:",
    ]
    for block in view.get("blocks") or []:
        lines.append(
            f"- block {block.get('block_id')} size={block.get('size')} "
            f"defined_vars={', '.join(block.get('defined_vars') or [])}"
        )
        lines.append(
            f"  cross_block_uses: {', '.join(block.get('cross_block_uses') or [])}"
        )
        for eq in block.get("equations") or []:
            lines.append(
                f"  line {eq.get('line_start')}: {eq.get('equation')}"
            )
    lines.append("=== end_modelica_blt_proxy_view ===")
    return "\n".join(lines)

