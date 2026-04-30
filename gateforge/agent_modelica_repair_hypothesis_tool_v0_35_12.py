from __future__ import annotations

import json
from typing import Any

SEMANTIC_TYPES = {
    "connector_flow_ownership",
    "reusable_contract_boundary",
    "local_implementation_equations",
    "connection_topology",
    "equation_balance_only",
    "unknown",
}


def get_repair_hypothesis_tool_defs() -> list[dict[str, Any]]:
    return [
        {
            "name": "record_repair_hypothesis",
            "description": (
                "Record the LLM's explicit repair hypothesis before testing a candidate. Audit-only; does not "
                "generate patches, select candidates, submit, or change the model."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "semantic_type": {
                        "type": "string",
                        "enum": sorted(SEMANTIC_TYPES),
                        "description": "The suspected semantic failure class.",
                    },
                    "target_boundary": {
                        "type": "string",
                        "description": "Where the LLM thinks the repair belongs, such as probe contract, local implementation, or topology.",
                    },
                    "candidate_strategy": {
                        "type": "string",
                        "description": "The structural repair strategy the LLM intends to test next.",
                    },
                    "expected_equation_delta": {
                        "type": "integer",
                        "description": "Expected net equation-count change for the next candidate.",
                    },
                    "fallback_hypothesis": {
                        "type": "string",
                        "description": "A different hypothesis to try if this candidate fails.",
                    },
                },
                "required": [
                    "semantic_type",
                    "target_boundary",
                    "candidate_strategy",
                    "expected_equation_delta",
                    "fallback_hypothesis",
                ],
            },
        }
    ]


def dispatch_repair_hypothesis_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "record_repair_hypothesis":
        return json.dumps({"error": f"unknown_repair_hypothesis_tool:{name}"}, sort_keys=True)
    semantic_type = str(arguments.get("semantic_type") or "").strip()
    target_boundary = str(arguments.get("target_boundary") or "").strip()
    candidate_strategy = str(arguments.get("candidate_strategy") or "").strip()
    fallback_hypothesis = str(arguments.get("fallback_hypothesis") or "").strip()
    try:
        expected_equation_delta = int(arguments.get("expected_equation_delta"))
    except (TypeError, ValueError):
        return json.dumps({"error": "expected_equation_delta_must_be_integer"}, sort_keys=True)
    if semantic_type not in SEMANTIC_TYPES:
        return json.dumps({"error": "invalid_semantic_type", "allowed": sorted(SEMANTIC_TYPES)}, sort_keys=True)
    if not target_boundary or not candidate_strategy or not fallback_hypothesis:
        return json.dumps({"error": "target_boundary_candidate_strategy_and_fallback_are_required"}, sort_keys=True)
    return json.dumps(
        {
            "hypothesis_recorded": True,
            "semantic_type": semantic_type,
            "target_boundary": target_boundary,
            "candidate_strategy": candidate_strategy,
            "expected_equation_delta": expected_equation_delta,
            "fallback_hypothesis": fallback_hypothesis,
            "discipline": {
                "audit_only": True,
                "auto_submit": False,
                "candidate_selected": False,
                "patch_generated": False,
            },
            "guidance": "This is an audit record only. The LLM must still write and test the candidate itself.",
        },
        sort_keys=True,
    )
