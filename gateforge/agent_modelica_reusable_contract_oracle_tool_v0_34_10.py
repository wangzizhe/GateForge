from __future__ import annotations

import json
from typing import Any

from .agent_modelica_reusable_contract_oracle_v0_34_9 import evaluate_reusable_contract_candidate

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "reusable_contract_oracle_diagnostic",
        "description": (
            "Audit whether a candidate appears to keep flow-ownership repair inside reusable nested contracts. "
            "Diagnostic-only: it does not generate patches, select candidates, or submit final answers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {
                    "type": "string",
                    "description": "Complete Modelica model source code to audit.",
                },
            },
            "required": ["model_text"],
        },
    }
]


def get_reusable_contract_oracle_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_reusable_contract_oracle_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "reusable_contract_oracle_diagnostic":
        return json.dumps({"error": f"unknown_reusable_contract_oracle_tool:{name}"})
    model_text = str(arguments.get("model_text") or "")
    if not model_text.strip():
        return json.dumps({"error": "empty_model_text"})
    payload = evaluate_reusable_contract_candidate(model_text)
    payload["tool_name"] = name
    payload["guidance"] = (
        "This oracle is audit-only. If OMC also passes and this diagnostic matches the explicit task constraints, "
        "the LLM must still decide whether to call submit_final itself."
    )
    return json.dumps(payload, sort_keys=True)
