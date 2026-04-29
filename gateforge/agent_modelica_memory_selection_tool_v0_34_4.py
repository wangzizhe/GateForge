from __future__ import annotations

import json
from typing import Any

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "record_semantic_memory_selection",
        "description": (
            "Record which semantic memory units the LLM intends to use or reject before testing a repair. "
            "Diagnostic-only: it does not retrieve, rank, generate patches, select candidates, or submit final answers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "selected_unit_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Semantic memory unit ids the LLM chooses to apply.",
                },
                "rejected_unit_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Semantic memory unit ids the LLM chooses not to apply.",
                },
                "rationale": {
                    "type": "string",
                    "description": "Why the selected memory matches the current compiler symptoms and task constraints.",
                },
                "risk": {
                    "type": "string",
                    "description": "What repair risk the LLM will avoid while using the memory.",
                },
            },
            "required": ["selected_unit_ids", "rationale"],
        },
    }
]


def _clean_list(values: list[Any] | None) -> list[str]:
    return [str(item).strip() for item in (values or []) if str(item).strip()]


def record_semantic_memory_selection(
    *,
    selected_unit_ids: list[Any] | None = None,
    rejected_unit_ids: list[Any] | None = None,
    rationale: str = "",
    risk: str = "",
) -> str:
    selected = _clean_list(selected_unit_ids)
    rejected = _clean_list(rejected_unit_ids)
    overlap = sorted(set(selected) & set(rejected))
    payload = {
        "diagnostic_only": True,
        "patch_generated": False,
        "candidate_selected": False,
        "auto_submit": False,
        "retrieval_performed": False,
        "selected_unit_count": len(selected),
        "rejected_unit_count": len(rejected),
        "overlap_unit_ids": overlap,
        "selection_recorded": bool(selected),
        "rationale_recorded": bool(str(rationale).strip()),
        "risk_recorded": bool(str(risk).strip()),
        "guidance": (
            "This tool only records the LLM's own semantic-memory choice. "
            "The LLM must still write, check, simulate, and submit candidates itself."
        ),
    }
    return json.dumps(payload, sort_keys=True)


def get_memory_selection_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_memory_selection_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "record_semantic_memory_selection":
        return json.dumps({"error": f"unknown_memory_selection_tool:{name}"})
    selected = arguments.get("selected_unit_ids") if isinstance(arguments.get("selected_unit_ids"), list) else []
    rejected = arguments.get("rejected_unit_ids") if isinstance(arguments.get("rejected_unit_ids"), list) else []
    return record_semantic_memory_selection(
        selected_unit_ids=selected,
        rejected_unit_ids=rejected,
        rationale=str(arguments.get("rationale") or ""),
        risk=str(arguments.get("risk") or ""),
    )
