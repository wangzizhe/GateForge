from __future__ import annotations

import json
from typing import Any

from .agent_modelica_omc_unmatched_flow_tool_v0_35_20 import _unmatched_variables

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "residual_hypothesis_consistency_check",
        "description": (
            "Check whether a recorded repair hypothesis is consistent with compiler-named unmatched flow residuals. "
            "Audit-only; does not generate patches, select candidates, or submit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "omc_output": {"type": "string", "description": "Recent OMC output containing residual warnings."},
                "expected_equation_delta": {
                    "type": "integer",
                    "description": "The net equation-count change the LLM intends to test.",
                },
                "candidate_strategy": {
                    "type": "string",
                    "description": "The LLM's intended structural candidate strategy.",
                },
            },
            "required": ["omc_output", "expected_equation_delta", "candidate_strategy"],
        },
    }
]


def residual_hypothesis_consistency_check(
    *,
    omc_output: str,
    expected_equation_delta: int,
    candidate_strategy: str,
) -> str:
    variables = _unmatched_variables(omc_output)
    flow_variables = [variable for variable in variables if variable.endswith(".i")]
    delta_matches_named_residual = int(expected_equation_delta) == len(flow_variables)
    over_residual_delta = int(expected_equation_delta) > len(flow_variables) and bool(flow_variables)
    return json.dumps(
        {
            "diagnostic_only": True,
            "patch_generated": False,
            "candidate_selected": False,
            "submitted": False,
            "unmatched_flow_variable_count": len(flow_variables),
            "expected_equation_delta": int(expected_equation_delta),
            "delta_matches_named_residual": delta_matches_named_residual,
            "over_residual_delta": over_residual_delta,
            "candidate_strategy_recorded": str(candidate_strategy or ""),
            "interpretation": [
                "This check compares the LLM's stated equation-count delta with variables named by OMC.",
                "A mismatch is a critique of the hypothesis, not a patch or candidate choice.",
                "The LLM must still design, test, and submit any repair itself.",
            ],
        },
        sort_keys=True,
    )


def get_residual_hypothesis_consistency_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_residual_hypothesis_consistency_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "residual_hypothesis_consistency_check":
        return json.dumps({"error": f"unknown_residual_hypothesis_consistency_tool:{name}"}, sort_keys=True)
    try:
        expected_equation_delta = int(arguments.get("expected_equation_delta"))
    except (TypeError, ValueError):
        return json.dumps({"error": "expected_equation_delta_must_be_integer"}, sort_keys=True)
    omc_output = str(arguments.get("omc_output") or "")
    candidate_strategy = str(arguments.get("candidate_strategy") or "")
    if not omc_output.strip() or not candidate_strategy.strip():
        return json.dumps({"error": "omc_output_and_candidate_strategy_required"}, sort_keys=True)
    return residual_hypothesis_consistency_check(
        omc_output=omc_output,
        expected_equation_delta=expected_equation_delta,
        candidate_strategy=candidate_strategy,
    )
