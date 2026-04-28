from __future__ import annotations

import json
import re
from typing import Any

_MODEL_START_RE = re.compile(r"^\s*(?P<partial>partial\s+)?model\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_MODEL_END_RE = re.compile(r"^\s*end\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;")
_EXTENDS_RE = re.compile(r"\bextends\s+([A-Za-z_][A-Za-z0-9_.]*)")
_REPLACEABLE_RE = re.compile(
    r"\breplaceable\s+model\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?P<array>\[[^\]]+\])?\s*=\s*"
    r"(?P<actual>[A-Za-z_][A-Za-z0-9_.]*)\s+constrainedby\s+(?P<base>[A-Za-z_][A-Za-z0-9_.]*)",
)
_CONNECTOR_FIELD_RE = re.compile(
    r"^\s*(?P<type>[A-Za-z_][A-Za-z0-9_.]*(?:Pin|Connector|Port))\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?P<array>\[[^\]]+\])?\s*;",
    re.MULTILINE,
)
_EQUATION_SECTION_RE = re.compile(r"\bequation\b(?P<body>.*)", re.DOTALL)

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "replaceable_partial_diagnostic",
        "description": (
            "Inspect replaceable model declarations, constrainedby base models, partial interfaces, "
            "connector fields, and flow-current equation shape. Diagnostic-only; never generates patches."
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


def _local_name(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def _equations(body: str) -> list[str]:
    match = _EQUATION_SECTION_RE.search(body)
    if not match:
        return []
    equations: list[str] = []
    for raw in match.group("body").split(";"):
        line = " ".join(raw.strip().split())
        if line and not line.startswith("//"):
            equations.append(line)
    return equations


def _model_rows(model_text: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    stack: list[dict[str, Any]] = []
    for line in model_text.splitlines():
        start = _MODEL_START_RE.match(line)
        if start:
            stack.append(
                {
                    "name": start.group("name"),
                    "is_partial": bool(start.group("partial")),
                    "lines": [],
                }
            )
            continue
        if stack:
            stack[-1]["lines"].append(line)
        end = _MODEL_END_RE.match(line)
        if end and stack and end.group("name") == stack[-1]["name"]:
            item = stack.pop()
            name = str(item["name"])
            body = "\n".join(str(raw) for raw in item["lines"])
            rows[name] = _model_row(name=name, is_partial=bool(item["is_partial"]), body=body)
            if stack:
                stack[-1]["lines"].append("\n".join(str(raw) for raw in item["lines"]))
    return rows


def _model_row(*, name: str, is_partial: bool, body: str) -> dict[str, Any]:
        equations = _equations(body)
        connector_fields = [
            {
                "name": field.group("name"),
                "type": field.group("type"),
                "is_array": bool(field.group("array")),
            }
            for field in _CONNECTOR_FIELD_RE.finditer(body)
        ]
        flow_equations = [eq for eq in equations if ".i" in eq]
        return {
            "name": name,
            "is_partial": is_partial,
            "extends": [_local_name(item) for item in _EXTENDS_RE.findall(body)],
            "connector_fields": connector_fields,
            "equation_count": len(equations),
            "flow_equations": flow_equations,
            "flow_equation_count": len(flow_equations),
        }


def _replaceable_rows(model_text: str) -> list[dict[str, Any]]:
    return [
        {
            "name": match.group("name"),
            "actual_model": _local_name(match.group("actual")),
            "constrainedby": _local_name(match.group("base")),
            "is_array": bool(match.group("array")),
        }
        for match in _REPLACEABLE_RE.finditer(model_text)
    ]


def _risks(replaceables: list[dict[str, Any]], models: dict[str, dict[str, Any]]) -> list[str]:
    risks: list[str] = []
    for repl in replaceables:
        actual = models.get(str(repl["actual_model"]), {})
        base = models.get(str(repl["constrainedby"]), {})
        if repl.get("is_array"):
            risks.append(f"{repl['name']}:replaceable_array")
        if base.get("is_partial"):
            risks.append(f"{repl['name']}:constrainedby_partial_base")
        if base.get("connector_fields") and not base.get("flow_equations"):
            risks.append(f"{repl['name']}:base_has_connector_fields_without_flow_equations")
        if actual.get("flow_equations") and not base.get("flow_equations"):
            risks.append(f"{repl['name']}:actual_adds_flow_equations_not_present_in_base")
        if actual.get("flow_equations") and base.get("flow_equations"):
            risks.append(f"{repl['name']}:base_and_actual_both_have_flow_equations")
        if int(actual.get("flow_equation_count") or 0) != int(base.get("flow_equation_count") or 0):
            risks.append(f"{repl['name']}:flow_equation_count_mismatch")
    return sorted(set(risks))


def replaceable_partial_diagnostic(model_text: str) -> str:
    models = _model_rows(model_text)
    replaceables = _replaceable_rows(model_text)
    payload = {
        "diagnostic_only": True,
        "replaceable_declarations": replaceables,
        "models": models,
        "risks": _risks(replaceables, models),
        "risk_count": len(_risks(replaceables, models)),
        "patch_generated": False,
    }
    return json.dumps(payload, sort_keys=True)


def get_replaceable_partial_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_replaceable_partial_tool(name: str, arguments: dict) -> str:
    if name != "replaceable_partial_diagnostic":
        return json.dumps({"error": f"unknown_replaceable_partial_tool:{name}"})
    model_text = str(arguments.get("model_text") or "")
    if not model_text.strip():
        return json.dumps({"error": "empty_model_text"})
    return replaceable_partial_diagnostic(model_text)
