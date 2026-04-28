from __future__ import annotations

import json
from typing import Any

from .agent_modelica_replaceable_partial_tool_v0_29_16 import replaceable_partial_diagnostic

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "replaceable_partial_policy_check",
        "description": (
            "Check whether a candidate repair for replaceable/partial Modelica models repeats risky policy moves, "
            "such as adding flow equations to constrainedby partial bases while derived implementations already "
            "define flow behavior. Diagnostic-only; never generates patches or selects candidates."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {"type": "string", "description": "Candidate Modelica model source code."},
            },
            "required": ["model_text"],
        },
    }
]


def _model_has_flow_equation(row: dict[str, Any]) -> bool:
    return bool(row.get("flow_equations"))


def _replaceable_policy_risks(model_text: str) -> list[dict[str, Any]]:
    diagnostic = json.loads(replaceable_partial_diagnostic(model_text))
    models = diagnostic.get("models") if isinstance(diagnostic.get("models"), dict) else {}
    risks: list[dict[str, Any]] = []
    for repl in diagnostic.get("replaceable_declarations", []):
        if not isinstance(repl, dict):
            continue
        name = str(repl.get("name") or "")
        actual_name = str(repl.get("actual_model") or "")
        base_name = str(repl.get("constrainedby") or "")
        actual = models.get(actual_name, {}) if isinstance(models.get(actual_name), dict) else {}
        base = models.get(base_name, {}) if isinstance(models.get(base_name), dict) else {}
        base_has_flow = _model_has_flow_equation(base)
        actual_has_flow = _model_has_flow_equation(actual)
        if bool(base.get("is_partial")) and base_has_flow and actual_has_flow:
            risks.append(
                {
                    "replaceable": name,
                    "risk": "partial_base_flow_equation_duplicates_derived_flow_behavior",
                    "why_it_matters": (
                        "The constrainedby base is partial but now contains flow-current equations while the actual "
                        "implementation also contains flow-current equations. This often repeats the already-failed "
                        "base-equation repair policy and can produce duplicate or circular equations after flattening."
                    ),
                }
            )
        if bool(base.get("is_partial")) and base_has_flow and not actual_has_flow:
            risks.append(
                {
                    "replaceable": name,
                    "risk": "partial_base_now_owns_flow_behavior",
                    "why_it_matters": (
                        "The constrainedby base is partial and now owns flow-current behavior. Verify this is a "
                        "contract-level change rather than moving implementation equations into the interface."
                    ),
                }
            )
        if not base_has_flow and actual_has_flow:
            risks.append(
                {
                    "replaceable": name,
                    "risk": "implementation_level_flow_behavior_kept_in_actual_model",
                    "why_it_matters": (
                        "Flow-current behavior remains in the actual implementation rather than the partial base. "
                        "This is not a failure by itself; continue validating with OMC instead of moving the same "
                        "equation into the base just to satisfy equation counts."
                    ),
                }
            )
    return risks


def replaceable_partial_policy_check(model_text: str) -> str:
    risks = _replaceable_policy_risks(model_text)
    payload = {
        "diagnostic_only": True,
        "patch_generated": False,
        "candidate_selected": False,
        "policy_scope": "replaceable_partial_flow_contract",
        "risk_count": len(risks),
        "risks": risks,
        "guidance": (
            "Use this as a policy check before another OMC call. If the candidate moved flow-current equations into "
            "a partial constrainedby base after previous compiler failures, reconsider that repair policy. This tool "
            "does not provide a patch; the LLM must choose and test the next candidate."
        ),
    }
    return json.dumps(payload, sort_keys=True)


def get_replaceable_policy_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_replaceable_policy_tool(name: str, arguments: dict) -> str:
    if name != "replaceable_partial_policy_check":
        return json.dumps({"error": f"unknown_replaceable_policy_tool:{name}"})
    model_text = str(arguments.get("model_text") or "")
    if not model_text.strip():
        return json.dumps({"error": "empty_model_text"})
    return replaceable_partial_policy_check(model_text)
