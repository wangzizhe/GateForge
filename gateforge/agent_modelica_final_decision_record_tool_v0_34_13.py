from __future__ import annotations

import json
from typing import Any


DECISION_VALUES = {"submit", "continue", "abandon"}


def get_final_decision_record_tool_defs() -> list[dict[str, Any]]:
    return [
        {
            "name": "record_final_decision_rationale",
            "description": (
                "Record the LLM's explicit final-decision rationale after a candidate has passed available checks. "
                "This is audit-only: it does not submit, select a candidate, generate a patch, or change the model."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": sorted(DECISION_VALUES),
                        "description": "Whether the LLM intends to submit, keep searching, or abandon.",
                    },
                    "evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Concrete evidence already observed, such as OMC pass, simulation pass, or oracle pass.",
                    },
                    "remaining_blockers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Explicit reasons not to submit yet. Use an empty list if there are no blockers.",
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Short explanation of the decision in the LLM's own words.",
                    },
                },
                "required": ["decision", "evidence", "remaining_blockers", "rationale"],
            },
        }
    ]


def dispatch_final_decision_record_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "record_final_decision_rationale":
        return json.dumps({"error": f"unknown tool: {name}"}, sort_keys=True)
    decision = str(arguments.get("decision") or "").strip()
    evidence = [str(item) for item in arguments.get("evidence", []) if str(item).strip()]
    remaining_blockers = [str(item) for item in arguments.get("remaining_blockers", []) if str(item).strip()]
    rationale = str(arguments.get("rationale") or "").strip()
    if decision not in DECISION_VALUES:
        return json.dumps({"error": "decision must be submit, continue, or abandon"}, sort_keys=True)
    if not evidence:
        return json.dumps({"error": "evidence must include at least one observed signal"}, sort_keys=True)
    if not rationale:
        return json.dumps({"error": "rationale is required"}, sort_keys=True)
    return json.dumps(
        {
            "decision_recorded": True,
            "decision": decision,
            "evidence": evidence,
            "remaining_blockers": remaining_blockers,
            "has_remaining_blockers": bool(remaining_blockers),
            "rationale": rationale,
            "discipline": {
                "audit_only": True,
                "auto_submit": False,
                "candidate_selected": False,
                "patch_generated": False,
            },
            "guidance": "This record is audit-only. If the decision is submit, the LLM must still call submit_final itself.",
        },
        sort_keys=True,
    )
