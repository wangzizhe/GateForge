from __future__ import annotations

import json
import re
from typing import Any

_CONNECTOR_RE = re.compile(
    r"\bconnector\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b(?P<body>.*?)\bend\s+(?P=name)\s*;",
    re.DOTALL,
)
_MODEL_RE = re.compile(
    r"(?P<partial>partial\s+)?model\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b(?P<body>.*?)\bend\s+(?P=name)\s*;",
    re.DOTALL,
)
_MODEL_START_RE = re.compile(r"^\s*(?P<partial>partial\s+)?model\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_MODEL_END_RE = re.compile(r"^\s*end\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;")
_CONNECT_RE = re.compile(r"\bconnect\s*\((?P<a>[^,]+),(?P<b>[^)]+)\)\s*;")
_EQUATION_SECTION_RE = re.compile(r"\bequation\b(?P<body>.*)", re.DOTALL)
_FLOW_DECL_RE = re.compile(r"^\s*flow\s+[A-Za-z_][A-Za-z0-9_.]*\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "connector_flow_semantics_diagnostic",
        "description": (
            "Inspect connector flow-equation semantics after OMC reports under/over/singular systems or balanced "
            "equation counts without simulation success. Diagnostic-only; reports flow equation patterns and risks "
            "without generating patches, selecting candidates, or submitting."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {"type": "string", "description": "Modelica model source code."},
                "omc_output": {
                    "type": "string",
                    "description": "Optional recent OMC check/simulate output for context.",
                },
            },
            "required": ["model_text"],
        },
    }
]


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


def _connect_rows(model_text: str) -> list[dict[str, str]]:
    return [{"left": m.group("a").strip(), "right": m.group("b").strip()} for m in _CONNECT_RE.finditer(model_text)]


def _declared_connectors(model_text: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for match in _CONNECTOR_RE.finditer(model_text):
        flow_vars = _FLOW_DECL_RE.findall(match.group("body"))
        rows[match.group("name")] = {
            "name": match.group("name"),
            "flow_vars": flow_vars,
            "flow_var_count": len(flow_vars),
        }
    return rows


def _flow_equation_kind(equation: str) -> str:
    compact = equation.replace(" ", "")
    if not re.search(r"\.[A-Za-z_][A-Za-z0-9_]*\.?i\b|\bi\b", compact):
        return "not_flow_equation"
    if re.search(r"\.i=-[^=]+\.i$", compact) or re.search(r"\.i\+[^=]+\.i=0", compact):
        return "paired_flow_balance_constraint"
    if re.search(r"^[A-Za-z_][A-Za-z0-9_\[\].]*\.i=0(?:\.0)?$", compact):
        return "zero_current_constraint"
    if "/" in compact and ".v" in compact:
        return "conductance_or_resistance_law"
    if "+" in compact and ".i" in compact:
        return "aggregate_flow_constraint"
    return "other_flow_constraint"


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
        if not (stack and end and end.group("name") == stack[-1]["name"]):
            continue
        item = stack.pop()
        body = "\n".join(str(raw) for raw in item["lines"])
        equations = _equations(body)
        flow_equations = [eq for eq in equations if ".i" in eq or re.search(r"\bi\s*=", eq)]
        kind_counts: dict[str, int] = {}
        for eq in flow_equations:
            kind = _flow_equation_kind(eq)
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
        rows[str(item["name"])] = {
            "name": str(item["name"]),
            "is_partial": bool(item["is_partial"]),
            "flow_equation_count": len(flow_equations),
            "flow_equation_kind_counts": kind_counts,
            "flow_equation_examples": flow_equations[:6],
        }
    return rows


def _shared_roots(connects: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in connects:
        for side in (row["left"], row["right"]):
            root = side.split("[", 1)[0].split(".", 1)[0].strip()
            if root:
                counts[root] = counts.get(root, 0) + 1
    return {key: count for key, count in sorted(counts.items()) if count >= 3}


def _omc_state(omc_output: str) -> dict[str, Any]:
    text = str(omc_output or "")
    equation_counts = re.findall(r"has\s+(\d+)\s+equation\(s\)\s+and\s+(\d+)\s+variable\(s\)", text)
    latest = equation_counts[-1] if equation_counts else None
    return {
        "has_result_file": 'resultFile = "/workspace/' in text,
        "has_empty_result_file": 'resultFile = ""' in text,
        "latest_equation_count": int(latest[0]) if latest else None,
        "latest_variable_count": int(latest[1]) if latest else None,
        "balanced_equation_count": bool(latest and latest[0] == latest[1]),
        "mentions_singular": "singular" in text.lower(),
        "mentions_overdetermined": "overdetermined" in text.lower() or "too many equations" in text.lower(),
        "mentions_underdetermined": "underdetermined" in text.lower() or "not enough equations" in text.lower(),
    }


def _risks(*, models: dict[str, dict[str, Any]], connects: list[dict[str, str]], omc_state: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    if omc_state["balanced_equation_count"] and not omc_state["has_result_file"]:
        risks.append("balanced_equation_count_without_simulation_success")
    if _shared_roots(connects):
        risks.append("shared_connector_roots_create_large_connection_sets")
    for name, row in models.items():
        kind_counts = row["flow_equation_kind_counts"]
        if kind_counts.get("zero_current_constraint", 0) >= 4:
            risks.append(f"{name}:many_zero_current_constraints_can_overconstrain_flow_sets")
        if kind_counts.get("paired_flow_balance_constraint", 0) > 0:
            risks.append(f"{name}:paired_flow_balance_may_balance_counts_without_unique_semantics")
        if kind_counts.get("conductance_or_resistance_law", 0) > 0 and kind_counts.get("paired_flow_balance_constraint", 0) == 0:
            risks.append(f"{name}:one_sided_flow_law_may_leave_return_flow_semantics_ambiguous")
        if row["flow_equation_count"] == 0 and not row["is_partial"]:
            risks.append(f"{name}:no_internal_flow_equations")
    return sorted(set(risks))


def connector_flow_semantics_diagnostic(model_text: str, omc_output: str = "") -> str:
    connectors = _declared_connectors(model_text)
    models = _model_rows(model_text)
    connects = _connect_rows(model_text)
    state = _omc_state(omc_output)
    risks = _risks(models=models, connects=connects, omc_state=state)
    return json.dumps(
        {
            "diagnostic_only": True,
            "patch_generated": False,
            "candidate_selected": False,
            "submitted": False,
            "declared_connectors": connectors,
            "model_flow_summary": models,
            "connect_summary": {
                "connect_count": len(connects),
                "arrayed_connect_count": sum(1 for row in connects if "[" in row["left"] or "[" in row["right"]),
                "shared_connector_roots": _shared_roots(connects),
            },
            "omc_state": state,
            "semantic_risks": risks,
            "risk_count": len(risks),
            "interpretation": [
                "A balanced equation count is not equivalent to a successful simulation result.",
                "Flow equations should be interpreted together with connection sets, not only by counting equations.",
                "This diagnostic reports risks only; the LLM must still design, test, and submit any repair itself.",
            ],
        },
        sort_keys=True,
    )


def get_connector_flow_semantics_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_connector_flow_semantics_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "connector_flow_semantics_diagnostic":
        return json.dumps({"error": f"unknown_connector_flow_semantics_tool:{name}"}, sort_keys=True)
    model_text = str(arguments.get("model_text") or "")
    if not model_text.strip():
        return json.dumps({"error": "empty_model_text"}, sort_keys=True)
    return connector_flow_semantics_diagnostic(model_text, str(arguments.get("omc_output") or ""))
