from __future__ import annotations

import json
import re
from typing import Any

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "omc_unmatched_flow_diagnostic",
        "description": (
            "Extract compiler-named unmatched flow variables from OMC output and group them by array root. "
            "Diagnostic-only; does not generate patches, select candidates, or submit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "omc_output": {"type": "string", "description": "Recent OMC checkModel or simulate output."},
            },
            "required": ["omc_output"],
        },
    }
]


def _array_root(variable: str) -> str:
    return re.sub(r"\[\d+\]", "[]", str(variable))


def _unmatched_variables(omc_output: str) -> list[str]:
    variables: list[str] = []
    for match in re.finditer(
        r"Variable\s+([A-Za-z_][A-Za-z0-9_\.\[\]]+)\s+does not have any remaining equation",
        str(omc_output or ""),
    ):
        variable = match.group(1)
        if variable not in variables:
            variables.append(variable)
    return variables


def _flow_groups(variables: list[str]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = {}
    for variable in variables:
        if not variable.endswith(".i"):
            continue
        grouped.setdefault(_array_root(variable), []).append(variable)
    return [
        {
            "array_root": root,
            "variable_count": len(values),
            "variables": sorted(values),
        }
        for root, values in sorted(grouped.items())
    ]


def omc_unmatched_flow_diagnostic(omc_output: str) -> str:
    variables = _unmatched_variables(omc_output)
    flow_variables = [variable for variable in variables if variable.endswith(".i")]
    return json.dumps(
        {
            "diagnostic_only": True,
            "patch_generated": False,
            "candidate_selected": False,
            "submitted": False,
            "unmatched_variable_count": len(variables),
            "unmatched_flow_variable_count": len(flow_variables),
            "unmatched_variables": variables,
            "unmatched_flow_variables": flow_variables,
            "flow_variable_groups": _flow_groups(flow_variables),
            "interpretation": [
                "These variables are extracted from the current OMC output, not from hidden reference repairs.",
                "Compiler-named unmatched variables are evidence about the current residual, not a patch.",
                "The LLM must still design, test, and submit any repair itself.",
            ],
        },
        sort_keys=True,
    )


def get_omc_unmatched_flow_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_omc_unmatched_flow_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "omc_unmatched_flow_diagnostic":
        return json.dumps({"error": f"unknown_omc_unmatched_flow_tool:{name}"}, sort_keys=True)
    omc_output = str(arguments.get("omc_output") or "")
    if not omc_output.strip():
        return json.dumps({"error": "empty_omc_output"}, sort_keys=True)
    return omc_unmatched_flow_diagnostic(omc_output)
