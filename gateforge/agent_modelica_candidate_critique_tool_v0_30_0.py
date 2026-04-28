from __future__ import annotations

import json
from typing import Any

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "candidate_acceptance_critique",
        "description": (
            "Critique whether a candidate repair should be accepted after OMC evidence. "
            "Diagnostic-only: it does not generate patches, select candidates, or submit final answers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "omc_passed": {
                    "type": "boolean",
                    "description": "Whether the candidate has passed check_model/simulation evidence.",
                },
                "task_constraints": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Explicit task constraints that the candidate must satisfy.",
                },
                "concern": {
                    "type": "string",
                    "description": "The LLM's concrete reason for not submitting the candidate.",
                },
            },
            "required": ["omc_passed"],
        },
    }
]

_CONSTRAINT_TERMS = ("constraint", "requirement", "task", "oracle", "must", "preserve", "keep")


def _has_constraint_citation(concern: str, constraints: list[str]) -> bool:
    normalized = concern.lower()
    if any(term in normalized for term in _CONSTRAINT_TERMS):
        return True
    return any(constraint.lower()[:24] in normalized for constraint in constraints if constraint.strip())


def candidate_acceptance_critique(
    *,
    omc_passed: bool,
    task_constraints: list[str] | None = None,
    concern: str = "",
) -> str:
    constraints = [str(item) for item in (task_constraints or []) if str(item).strip()]
    concern_text = str(concern or "").strip()
    cites_constraint = _has_constraint_citation(concern_text, constraints)
    if not omc_passed:
        verdict = "continue_repair"
        reason = "No OMC success evidence was reported for this candidate."
    elif concern_text and cites_constraint:
        verdict = "review_named_constraint"
        reason = "The concern cites an explicit task/oracle boundary; the LLM should verify that boundary before submitting."
    elif concern_text:
        verdict = "no_encoded_blocker_found"
        reason = "The concern is not tied to an explicit task constraint or oracle requirement."
    else:
        verdict = "no_encoded_blocker_found"
        reason = "The candidate has OMC success evidence and no remaining explicit concern was provided."
    payload = {
        "diagnostic_only": True,
        "patch_generated": False,
        "candidate_selected": False,
        "auto_submit": False,
        "verdict": verdict,
        "reason": reason,
        "omc_passed": bool(omc_passed),
        "constraint_citation_seen": cites_constraint,
        "explicit_constraint_count": len(constraints),
        "guidance": (
            "This critique is advisory. If no encoded blocker is found, the LLM should decide whether to call "
            "submit_final with the same successful candidate. The wrapper will not submit automatically."
        ),
    }
    return json.dumps(payload, sort_keys=True)


def get_candidate_critique_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_candidate_critique_tool(name: str, arguments: dict) -> str:
    if name != "candidate_acceptance_critique":
        return json.dumps({"error": f"unknown_candidate_critique_tool:{name}"})
    constraints = arguments.get("task_constraints") if isinstance(arguments.get("task_constraints"), list) else []
    return candidate_acceptance_critique(
        omc_passed=bool(arguments.get("omc_passed")),
        task_constraints=[str(item) for item in constraints],
        concern=str(arguments.get("concern") or ""),
    )
