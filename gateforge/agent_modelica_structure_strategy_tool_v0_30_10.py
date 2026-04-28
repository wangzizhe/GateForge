from __future__ import annotations

import json
from typing import Any

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "record_structure_strategies",
        "description": (
            "Record distinct structural repair strategies before testing more candidates. "
            "Diagnostic-only: it does not generate patches, select candidates, or submit final answers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "strategies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Two or three structurally distinct repair strategies to consider.",
                },
                "selected_strategy": {
                    "type": "string",
                    "description": "The strategy the LLM intends to test next.",
                },
                "reason": {
                    "type": "string",
                    "description": "Why this strategy is structurally different from previous candidates.",
                },
            },
            "required": ["strategies", "selected_strategy"],
        },
    }
]


def record_structure_strategies(
    *,
    strategies: list[str] | None = None,
    selected_strategy: str = "",
    reason: str = "",
) -> str:
    clean_strategies = [str(item).strip() for item in (strategies or []) if str(item).strip()]
    unique_strategy_count = len({item.lower() for item in clean_strategies})
    payload: dict[str, Any] = {
        "diagnostic_only": True,
        "patch_generated": False,
        "candidate_selected": False,
        "auto_submit": False,
        "strategy_count": len(clean_strategies),
        "unique_strategy_count": unique_strategy_count,
        "selected_strategy_recorded": bool(str(selected_strategy).strip()),
        "reason_recorded": bool(str(reason).strip()),
        "guidance": (
            "This tool only records the LLM's plan. The LLM must still write and test the next candidate itself. "
            "Prefer strategies that change interface/equation placement, not only names or formatting."
        ),
    }
    return json.dumps(payload, sort_keys=True)


def get_structure_strategy_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_structure_strategy_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "record_structure_strategies":
        return json.dumps({"error": f"unknown_structure_strategy_tool:{name}"})
    strategies = arguments.get("strategies") if isinstance(arguments.get("strategies"), list) else []
    return record_structure_strategies(
        strategies=[str(item) for item in strategies],
        selected_strategy=str(arguments.get("selected_strategy") or ""),
        reason=str(arguments.get("reason") or ""),
    )
