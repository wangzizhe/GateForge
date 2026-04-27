from __future__ import annotations

import json
import re
from typing import Any

_CONNECTOR_RE = re.compile(
    r"\bconnector\s+([A-Za-z_][A-Za-z0-9_]*)\b(?P<body>.*?)\bend\s+\1\s*;",
    re.DOTALL,
)
_DECL_RE = re.compile(
    r"^\s*(?P<prefix>(?:flow|stream)\s+)?(?P<type>[A-Za-z_][A-Za-z0-9_.]*)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_CONNECT_RE = re.compile(r"\bconnect\s*\((?P<a>[^,]+),(?P<b>[^)]+)\)\s*;")
_DIRECT_FIELD_EQ_RE = re.compile(
    r"(?P<lhs>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s*="
)

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "connector_balance_diagnostic",
        "description": (
            "Inspect custom Modelica connector declarations and related connect/direct field equation usage. "
            "Reports flow/potential declaration counts and connector-balance risks only. "
            "This is diagnostic-only and does not generate a repair patch."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {"type": "string", "description": "Modelica model source code (omit to use current model)."},
            },
            "required": [],
        },
    }
]


def _connector_declarations(body: str) -> list[dict[str, str | bool]]:
    declarations: list[dict[str, str | bool]] = []
    for match in _DECL_RE.finditer(body):
        prefix = (match.group("prefix") or "").strip()
        var_type = match.group("type")
        name = match.group("name")
        if var_type in {"parameter", "input", "output"}:
            continue
        declarations.append(
            {
                "name": name,
                "type": var_type,
                "is_flow": prefix == "flow",
                "is_stream": prefix == "stream",
            }
        )
    return declarations


def _connector_rows(model_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in _CONNECTOR_RE.finditer(model_text):
        name = match.group(1)
        declarations = _connector_declarations(match.group("body"))
        flow_vars = [str(item["name"]) for item in declarations if item.get("is_flow")]
        potential_like_vars = [
            str(item["name"])
            for item in declarations
            if not item.get("is_flow") and not item.get("is_stream")
        ]
        rows.append(
            {
                "name": name,
                "declarations": declarations,
                "flow_vars": flow_vars,
                "potential_like_vars": potential_like_vars,
                "flow_count": len(flow_vars),
                "potential_like_count": len(potential_like_vars),
                "balance_risk": len(flow_vars) != len(potential_like_vars),
            }
        )
    return rows


def _usage_rows(model_text: str) -> dict[str, Any]:
    connects = [
        {"left": match.group("a").strip(), "right": match.group("b").strip()}
        for match in _CONNECT_RE.finditer(model_text)
    ]
    direct_field_equations = sorted({match.group("lhs") for match in _DIRECT_FIELD_EQ_RE.finditer(model_text)})
    return {
        "connects": connects,
        "direct_field_equation_lhs": direct_field_equations,
        "direct_field_equation_count": len(direct_field_equations),
    }


def connector_balance_diagnostic(model_text: str) -> str:
    connectors = _connector_rows(model_text)
    usage = _usage_rows(model_text)
    risks: list[str] = []
    for connector in connectors:
        if connector["balance_risk"]:
            risks.append(f"{connector['name']}:flow_potential_count_mismatch")
        if len(connector["flow_vars"]) > 1:
            risks.append(f"{connector['name']}:multiple_flow_variables")
    if usage["direct_field_equation_count"] > 0 and connectors:
        risks.append("custom_connector_direct_field_equations_present")
    payload = {
        "diagnostic_only": True,
        "connectors": connectors,
        "usage": usage,
        "risks": sorted(risks),
        "risk_count": len(set(risks)),
        "patch_generated": False,
    }
    return json.dumps(payload, sort_keys=True)


def get_connector_balance_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_connector_balance_tool(name: str, arguments: dict) -> str:
    if name != "connector_balance_diagnostic":
        return json.dumps({"error": f"unknown_connector_balance_tool:{name}"})
    model_text = str(arguments.get("model_text") or "")
    if not model_text.strip():
        return json.dumps({"error": "empty_model_text"})
    return connector_balance_diagnostic(model_text)
