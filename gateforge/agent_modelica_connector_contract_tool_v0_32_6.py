from __future__ import annotations

import json
import re
from typing import Any

_MODEL_START_RE = re.compile(r"^\s*(?P<partial>partial\s+)?model\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_MODEL_END_RE = re.compile(r"^\s*end\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;")
_CONNECTOR_START_RE = re.compile(r"^\s*connector\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_CONNECTOR_END_RE = re.compile(r"^\s*end\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;")
_FIELD_RE = re.compile(
    r"^\s*(?P<type>[A-Za-z_][A-Za-z0-9_.]*)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?P<array>\[[^\]]+\])?\s*;",
    re.MULTILINE,
)
_REPLACEABLE_RE = re.compile(
    r"\breplaceable\s+model\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?P<array>\[[^\]]+\])?\s*=\s*"
    r"(?P<actual>[A-Za-z_][A-Za-z0-9_.]*)\s+constrainedby\s+(?P<base>[A-Za-z_][A-Za-z0-9_.]*)",
)
_EXTENDS_RE = re.compile(r"\bextends\s+([A-Za-z_][A-Za-z0-9_.]*)")
_CONNECT_RE = re.compile(r"\bconnect\s*\((?P<a>[^,]+),(?P<b>[^)]+)\)\s*;")
_EQUATION_SECTION_RE = re.compile(r"\bequation\b(?P<body>.*)", re.DOTALL)

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "connector_contract_diagnostic",
        "description": (
            "Inspect arrayed connector buses, reusable probe/adapter contracts, flow variable ownership, "
            "and replaceable/partial interface boundaries. Diagnostic-only; reports semantic risks and "
            "does not generate patches, select candidates, or submit."
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
    rows: list[str] = []
    for raw in match.group("body").split(";"):
        row = " ".join(raw.strip().split())
        if row and not row.startswith("//"):
            rows.append(row)
    return rows


def _declared_connectors(model_text: str) -> dict[str, dict[str, Any]]:
    connectors: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    for line in model_text.splitlines():
        start = _CONNECTOR_START_RE.match(line)
        if start:
            current = {"name": start.group("name"), "lines": []}
            continue
        if current is not None:
            current["lines"].append(line)
        end = _CONNECTOR_END_RE.match(line)
        if current is not None and end and end.group("name") == current["name"]:
            body = "\n".join(str(raw) for raw in current["lines"])
            flow_vars = re.findall(r"^\s*flow\s+[A-Za-z_][A-Za-z0-9_.]*\s+([A-Za-z_][A-Za-z0-9_]*)\b", body, re.MULTILINE)
            potential_vars = [
                name
                for name in re.findall(r"^\s*(?!flow\b|stream\b)(?:Real|Integer|Boolean)\s+([A-Za-z_][A-Za-z0-9_]*)\b", body, re.MULTILINE)
            ]
            connectors[str(current["name"])] = {
                "name": str(current["name"]),
                "flow_vars": flow_vars,
                "potential_vars": potential_vars,
                "flow_count": len(flow_vars),
                "potential_count": len(potential_vars),
            }
            current = None
    return connectors


def _model_rows(model_text: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    stack: list[dict[str, Any]] = []
    for line in model_text.splitlines():
        start = _MODEL_START_RE.match(line)
        if start:
            stack.append({"name": start.group("name"), "is_partial": bool(start.group("partial")), "lines": []})
            continue
        if stack:
            stack[-1]["lines"].append(line)
        end = _MODEL_END_RE.match(line)
        if stack and end and end.group("name") == stack[-1]["name"]:
            item = stack.pop()
            name = str(item["name"])
            body = "\n".join(str(raw) for raw in item["lines"])
            equations = _equations(body)
            fields = [
                {
                    "name": match.group("name"),
                    "type": _local_name(match.group("type")),
                    "is_array": bool(match.group("array")),
                }
                for match in _FIELD_RE.finditer(body)
                if _local_name(match.group("type")).lower().endswith(("pin", "connector", "port"))
            ]
            rows[name] = {
                "name": name,
                "is_partial": bool(item["is_partial"]),
                "extends": [_local_name(item) for item in _EXTENDS_RE.findall(body)],
                "connector_fields": fields,
                "array_connector_field_count": sum(1 for field in fields if field["is_array"]),
                "flow_equation_count": sum(1 for eq in equations if ".i" in eq),
                "potential_read_count": sum(1 for eq in equations if ".v" in eq),
                "connect_count": sum(1 for eq in equations if eq.startswith("connect(")),
            }
            if stack:
                stack[-1]["lines"].append(body)
    return rows


def _replaceables(model_text: str) -> list[dict[str, Any]]:
    return [
        {
            "name": match.group("name"),
            "is_array": bool(match.group("array")),
            "actual_model": _local_name(match.group("actual")),
            "constrainedby": _local_name(match.group("base")),
        }
        for match in _REPLACEABLE_RE.finditer(model_text)
    ]


def _connect_rows(model_text: str) -> list[dict[str, str]]:
    return [
        {"left": match.group("a").strip(), "right": match.group("b").strip()}
        for match in _CONNECT_RE.finditer(model_text)
    ]


def _arrayed_connect_count(connects: list[dict[str, str]]) -> int:
    return sum(1 for row in connects if "[" in row["left"] or "[" in row["right"])


def _shared_node_mentions(connects: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in connects:
        for side in (row["left"], row["right"]):
            root = side.split("[", 1)[0].split(".", 1)[0].strip()
            if root:
                counts[root] = counts.get(root, 0) + 1
    return {key: value for key, value in sorted(counts.items()) if value >= 3}


def _risks(
    *,
    models: dict[str, dict[str, Any]],
    replaceables: list[dict[str, Any]],
    connects: list[dict[str, str]],
) -> list[str]:
    risks: list[str] = []
    if _arrayed_connect_count(connects) >= 4:
        risks.append("arrayed_connectors_form_repeated_connection_sets")
    if _shared_node_mentions(connects):
        risks.append("shared_nodes_participate_in_multiple_connection_sets")
    for row in replaceables:
        actual = models.get(str(row["actual_model"]), {})
        base = models.get(str(row["constrainedby"]), {})
        if base.get("is_partial"):
            risks.append(f"{row['name']}:partial_constrainedby_contract")
        if int(base.get("array_connector_field_count") or 0) > 0:
            risks.append(f"{row['name']}:base_exposes_arrayed_connector_fields")
        if int(actual.get("potential_read_count") or 0) > 0 and int(actual.get("flow_equation_count") or 0) == 0:
            risks.append(f"{row['name']}:actual_reads_potential_without_flow_ownership")
        if int(actual.get("flow_equation_count") or 0) > 0 and int(base.get("flow_equation_count") or 0) == 0:
            risks.append(f"{row['name']}:actual_adds_flow_ownership_not_in_base_contract")
    return sorted(set(risks))


def connector_contract_diagnostic(model_text: str) -> str:
    connectors = _declared_connectors(model_text)
    models = _model_rows(model_text)
    replaceables = _replaceables(model_text)
    connects = _connect_rows(model_text)
    shared_nodes = _shared_node_mentions(connects)
    risks = _risks(models=models, replaceables=replaceables, connects=connects)
    payload = {
        "diagnostic_only": True,
        "patch_generated": False,
        "candidate_selected": False,
        "submitted": False,
        "declared_connectors": connectors,
        "replaceable_declarations": replaceables,
        "reusable_contract_models": {
            name: row
            for name, row in sorted(models.items())
            if row.get("is_partial") or row.get("connector_fields") or row.get("extends")
        },
        "connect_summary": {
            "connect_count": len(connects),
            "arrayed_connect_count": _arrayed_connect_count(connects),
            "shared_node_mentions": shared_nodes,
        },
        "semantic_risks": risks,
        "risk_count": len(risks),
        "interpretation": [
            "For connected flow variables, the ownership contract must be explicit in the component/interface design.",
            "A reusable probe/adapter that only reads potentials can still leave flow variables structurally unconstrained.",
            "Arrayed connects can repeat the same contract gap across several connection sets.",
        ],
    }
    return json.dumps(payload, sort_keys=True)


def get_connector_contract_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_connector_contract_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "connector_contract_diagnostic":
        return json.dumps({"error": f"unknown_connector_contract_tool:{name}"})
    model_text = str(arguments.get("model_text") or "")
    if not model_text.strip():
        return json.dumps({"error": "empty_model_text"})
    return connector_contract_diagnostic(model_text)
