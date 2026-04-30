from __future__ import annotations

import json
from typing import Any

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "record_candidate_preference_rationale",
        "description": (
            "Record why the LLM chooses one candidate over another when compiler evidence and symmetry/style "
            "preferences conflict. Audit-only; does not generate patches, select candidates, or submit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "selected_candidate": {"type": "string"},
                "rejected_candidate": {"type": "string"},
                "selected_expected_equation_delta": {"type": "integer"},
                "rejected_expected_equation_delta": {"type": "integer"},
                "compiler_named_residual_count": {"type": "integer"},
                "preference_basis": {
                    "type": "string",
                    "enum": [
                        "compiler_residual_match",
                        "modelica_style_symmetry",
                        "reusable_contract_cleanliness",
                        "physical_intuition",
                        "unknown",
                    ],
                },
                "why_compiler_evidence_wins_or_loses": {"type": "string"},
            },
            "required": [
                "selected_candidate",
                "rejected_candidate",
                "selected_expected_equation_delta",
                "rejected_expected_equation_delta",
                "compiler_named_residual_count",
                "preference_basis",
                "why_compiler_evidence_wins_or_loses",
            ],
        },
    }
]


def record_candidate_preference_rationale(
    *,
    selected_candidate: str,
    rejected_candidate: str,
    selected_expected_equation_delta: int,
    rejected_expected_equation_delta: int,
    compiler_named_residual_count: int,
    preference_basis: str,
    why_compiler_evidence_wins_or_loses: str,
) -> str:
    selected_matches = int(selected_expected_equation_delta) == int(compiler_named_residual_count)
    rejected_matches = int(rejected_expected_equation_delta) == int(compiler_named_residual_count)
    compiler_evidence_preferred = selected_matches and preference_basis == "compiler_residual_match"
    return json.dumps(
        {
            "diagnostic_only": True,
            "patch_generated": False,
            "candidate_selected": False,
            "submitted": False,
            "selected_candidate_recorded": bool(str(selected_candidate or "").strip()),
            "rejected_candidate_recorded": bool(str(rejected_candidate or "").strip()),
            "selected_expected_equation_delta": int(selected_expected_equation_delta),
            "rejected_expected_equation_delta": int(rejected_expected_equation_delta),
            "compiler_named_residual_count": int(compiler_named_residual_count),
            "selected_matches_residual_count": selected_matches,
            "rejected_matches_residual_count": rejected_matches,
            "preference_basis": preference_basis,
            "compiler_evidence_preferred": compiler_evidence_preferred,
            "rationale_recorded": bool(str(why_compiler_evidence_wins_or_loses or "").strip()),
            "interpretation": [
                "This records the LLM's candidate preference rationale only.",
                "It does not choose the candidate, generate Modelica code, or submit.",
                "The LLM must still write, test, and submit the selected candidate itself.",
            ],
        },
        sort_keys=True,
    )


def get_candidate_preference_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_candidate_preference_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "record_candidate_preference_rationale":
        return json.dumps({"error": f"unknown_candidate_preference_tool:{name}"}, sort_keys=True)
    try:
        selected_delta = int(arguments.get("selected_expected_equation_delta"))
        rejected_delta = int(arguments.get("rejected_expected_equation_delta"))
        residual_count = int(arguments.get("compiler_named_residual_count"))
    except (TypeError, ValueError):
        return json.dumps({"error": "delta_fields_must_be_integer"}, sort_keys=True)
    preference_basis = str(arguments.get("preference_basis") or "")
    if preference_basis not in {
        "compiler_residual_match",
        "modelica_style_symmetry",
        "reusable_contract_cleanliness",
        "physical_intuition",
        "unknown",
    }:
        return json.dumps({"error": "invalid_preference_basis"}, sort_keys=True)
    return record_candidate_preference_rationale(
        selected_candidate=str(arguments.get("selected_candidate") or ""),
        rejected_candidate=str(arguments.get("rejected_candidate") or ""),
        selected_expected_equation_delta=selected_delta,
        rejected_expected_equation_delta=rejected_delta,
        compiler_named_residual_count=residual_count,
        preference_basis=preference_basis,
        why_compiler_evidence_wins_or_loses=str(arguments.get("why_compiler_evidence_wins_or_loses") or ""),
    )
