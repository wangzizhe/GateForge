"""Modelica-native query helpers for GateForge v0.19.53.

This module intentionally starts with a conservative text parser. It returns
structural facts that can later be exposed as tools, but it does not diagnose
root causes, choose repairs, or edit model text.
"""
from __future__ import annotations

import re
from typing import Any


IDENT_RE = r"[A-Za-z_][A-Za-z0-9_]*"


def _top_level_equals_index(text: str) -> int | None:
    depth = 0
    in_string = False
    escape = False
    for idx, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "=" and depth == 0:
            return idx
    return None


def _strip_line_comment(line: str) -> str:
    in_string = False
    escape = False
    for idx in range(len(line) - 1):
        ch = line[idx]
        nxt = line[idx + 1]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "/" and nxt == "/":
            return line[:idx]
    return line


def _find_ident_tokens(text: str) -> set[str]:
    return set(re.findall(rf"\b{IDENT_RE}\b", text or ""))


def _find_reference_roots(text: str) -> set[str]:
    """Return identifier roots referenced in an expression-like statement."""
    roots: set[str] = set()
    for match in re.finditer(rf"\b{IDENT_RE}\b", text or ""):
        start = match.start()
        if start > 0 and text[start - 1] == ".":
            continue
        roots.add(match.group(0))
    return roots


def _statement_lines(lines: list[str], start: int) -> tuple[str, int]:
    parts = [lines[start]]
    idx = start
    while ";" not in lines[idx] and idx + 1 < len(lines):
        idx += 1
        parts.append(lines[idx])
    return "\n".join(parts), idx


def _parse_lhs(lhs_raw: str) -> tuple[str, str | None, bool]:
    lhs = lhs_raw.strip()
    der_match = re.match(rf"der\(\s*({IDENT_RE})\s*\)$", lhs)
    if der_match:
        name = der_match.group(1)
        return f"der({name})", name, True
    name_match = re.match(rf"({IDENT_RE})\b", lhs)
    if name_match:
        return name_match.group(1), None, False
    return lhs, None, False


def extract_real_declarations(model_text: str) -> list[dict[str, Any]]:
    """Return Real-like declarations from Modelica source text.

    Limitations (text-parser only):
    - Does NOT resolve declarations inherited through `extends`.
    - Does NOT trace `redeclare`, conditional components, or replaceable classes.
    - Handles one declared identifier per line; comma declarations are partial.
    - Does NOT parse algorithm-local variables.
    """
    declarations: list[dict[str, Any]] = []
    section = "public"
    decl_re = re.compile(
        rf"^\s*(?:(parameter|constant)\s+)?(?:(discrete)\s+)?Real\s+({IDENT_RE})\b([^;]*);"
    )
    for line_no, raw_line in enumerate(model_text.splitlines(), start=1):
        stripped = _strip_line_comment(raw_line).strip()
        if not stripped:
            continue
        if stripped == "protected":
            section = "protected"
            continue
        if stripped == "public":
            section = "public"
            continue
        match = decl_re.match(_strip_line_comment(raw_line))
        if not match:
            continue
        prefix, discrete, name, tail = match.groups()
        if prefix == "parameter":
            kind = "parameter"
        elif prefix == "constant":
            kind = "constant"
        elif discrete:
            kind = "discrete_real"
        else:
            kind = "real"
        declarations.append(
            {
                "name": name,
                "kind": kind,
                "line": line_no,
                "raw_line": raw_line,
                "section": section,
                "has_binding": _top_level_equals_index(tail or "") is not None,
            }
        )
    return declarations


def extract_equation_statements(model_text: str) -> list[dict[str, Any]]:
    """Return statements from equation sections in Modelica source text.

    Limitations (text-parser only):
    - Does NOT expand `connect()` into implicit equations.
    - `if`, `for`, `when`, and array equations may yield partial statements.
    - Does NOT flatten inherited equations from `extends`.
    - Does NOT parse algorithm sections.
    """
    lines = model_text.splitlines()
    statements: list[dict[str, Any]] = []
    in_equation = False
    section = ""
    idx = 0
    while idx < len(lines):
        stripped = _strip_line_comment(lines[idx]).strip()
        if re.match(r"^initial\s+equation\s*$", stripped):
            in_equation = True
            section = "initial_equation"
            idx += 1
            continue
        if stripped == "equation":
            in_equation = True
            section = "equation"
            idx += 1
            continue
        if re.match(r"^(algorithm|initial\s+algorithm|end\s+)", stripped):
            in_equation = False
            section = ""
            idx += 1
            continue
        if not in_equation or not stripped:
            idx += 1
            continue

        stmt, end_idx = _statement_lines(lines, idx)
        clean_stmt = "\n".join(_strip_line_comment(part) for part in stmt.splitlines()).strip()
        if not clean_stmt:
            idx = end_idx + 1
            continue
        is_connect = clean_stmt.lstrip().startswith("connect(")
        lhs = ""
        rhs = ""
        base_variable = None
        is_derivative_lhs = False
        if not is_connect:
            eq_idx = _top_level_equals_index(clean_stmt)
            if eq_idx is not None:
                lhs, base_variable, is_derivative_lhs = _parse_lhs(clean_stmt[:eq_idx].strip())
                rhs = clean_stmt[eq_idx + 1 :].rstrip(";").strip()
        statements.append(
            {
                "lhs": lhs,
                "rhs": rhs,
                "line_start": idx + 1,
                "line_end": end_idx + 1,
                "raw_text": stmt,
                "statement_text": clean_stmt,
                "section": section,
                "is_connect": is_connect,
                "is_derivative_lhs": is_derivative_lhs,
                "base_variable": base_variable,
            }
        )
        idx = end_idx + 1
    return statements


def who_defines(model_text: str, var_name: str) -> list[dict[str, Any]]:
    """Return equations where `var_name` appears on the LHS.

    Limitations (text-parser only):
    - Does NOT resolve declarations from `extends` clauses.
    - Does NOT trace through `redeclare` or conditional components.
    - Arrays, `when`, and `if` branches may yield partial results.
    - `connect()` statements are not expanded into implicit equations.
    """
    rows = []
    for stmt in extract_equation_statements(model_text):
        if stmt["lhs"] == var_name or stmt.get("base_variable") == var_name:
            rows.append(stmt)
    return rows


def who_uses(model_text: str, var_name: str) -> list[dict[str, Any]]:
    """Return equations where `var_name` appears outside the LHS.

    Limitations (text-parser only):
    - Does NOT resolve inherited equations from `extends`.
    - Does NOT trace `redeclare` or conditional components.
    - `connect()` is searched textually but not expanded into connection equations.
    - Algorithm sections are not parsed.
    """
    token = re.compile(rf"\b{re.escape(var_name)}\b")
    rows = []
    for stmt in extract_equation_statements(model_text):
        if stmt["is_connect"]:
            if token.search(stmt["statement_text"]):
                rows.append(stmt)
            continue
        if token.search(stmt["rhs"]):
            rows.append(stmt)
    return rows


def declared_but_unused(model_text: str) -> list[dict[str, Any]]:
    """Return non-parameter Real declarations that are not referenced.

    Limitations (text-parser only):
    - Does NOT inspect inherited use sites from `extends`.
    - Does NOT expand `connect()` into implicit equations.
    - Parameters with bindings are intentionally excluded from this defect-style
      list; unbound parameters are reported by `structural_signal_summary()`.
    """
    statements = extract_equation_statements(model_text)
    used: set[str] = set()
    for stmt in statements:
        used.update(_find_reference_roots(stmt["statement_text"]))
    rows = []
    for decl in extract_real_declarations(model_text):
        if decl["kind"] in {"parameter", "constant"}:
            continue
        if decl["name"] not in used:
            rows.append(decl)
    return rows


def structural_signal_summary(model_text: str) -> dict[str, Any]:
    """Return a conservative structural summary for Modelica source text.

    Limitations (text-parser only):
    - Does NOT flatten inherited declarations/equations.
    - Does NOT expand connection equations.
    - Does NOT diagnose repair actions; all fields are structural facts.
    """
    declarations = extract_real_declarations(model_text)
    equations = extract_equation_statements(model_text)
    declared = {d["name"] for d in declarations}
    defined = {stmt["lhs"] for stmt in equations if stmt["lhs"]}
    defined.update(stmt["base_variable"] for stmt in equations if stmt.get("base_variable"))
    used: set[str] = set()
    for stmt in equations:
        used.update(_find_reference_roots(stmt["rhs"]))
        if stmt["is_connect"]:
            used.update(_find_reference_roots(stmt["statement_text"]))
    declaration_by_name = {d["name"]: d for d in declarations}
    variables_with_no_defining_equation = []
    for decl in declarations:
        if decl["kind"] in {"parameter", "constant"}:
            continue
        if decl["name"] not in defined:
            variables_with_no_defining_equation.append(decl)
    unbound_parameters = [
        decl for decl in declarations
        if decl["kind"] == "parameter" and not decl["has_binding"]
    ]
    used_but_undeclared = sorted(
        name for name in used
        if name not in declared
        and name not in {"der", "time", "sin", "cos", "sqrt", "exp", "log", "connect"}
    )
    return {
        "declaration_count": len(declarations),
        "equation_count": sum(1 for stmt in equations if not stmt["is_connect"]),
        "connect_count": sum(1 for stmt in equations if stmt["is_connect"]),
        "variables_with_no_defining_equation": variables_with_no_defining_equation,
        "declared_but_unused": declared_but_unused(model_text),
        "unbound_parameters": unbound_parameters,
        "used_but_undeclared": [
            {"name": name, "declaration": declaration_by_name.get(name)}
            for name in used_but_undeclared
        ],
    }


def omc_query_model(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Reserved OMC scripting entry point for future versions.

    v0.19.53 intentionally ships the text-query layer first. OMC scripting
    wrappers will be added only after their load-path behavior is stable across
    standalone and library-backed models.
    """
    raise NotImplementedError("OMC scripting query wrappers are reserved for a later version.")
