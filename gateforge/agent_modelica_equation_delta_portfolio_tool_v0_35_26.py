from __future__ import annotations

import json
from typing import Any

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "record_equation_delta_candidate_portfolio",
        "description": (
            "Record multiple LLM-proposed repair candidate strategies with expected equation-count deltas. "
            "Audit-only; does not generate patches, select candidates, or submit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "compiler_named_residual_count": {
                    "type": "integer",
                    "description": "Number of compiler-named unmatched residual variables being targeted.",
                },
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "strategy": {"type": "string"},
                            "expected_equation_delta": {"type": "integer"},
                            "rationale": {"type": "string"},
                        },
                        "required": ["strategy", "expected_equation_delta", "rationale"],
                    },
                    "description": "Two or more structurally distinct candidate strategies proposed by the LLM.",
                },
                "selected_strategy": {
                    "type": "string",
                    "description": "The strategy the LLM intends to test next.",
                },
            },
            "required": ["compiler_named_residual_count", "candidates", "selected_strategy"],
        },
    }
]


def record_equation_delta_candidate_portfolio(
    *,
    compiler_named_residual_count: int,
    candidates: list[dict[str, Any]] | None,
    selected_strategy: str,
) -> str:
    clean_candidates: list[dict[str, Any]] = []
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            continue
        strategy = str(candidate.get("strategy") or "").strip()
        rationale = str(candidate.get("rationale") or "").strip()
        try:
            delta = int(candidate.get("expected_equation_delta"))
        except (TypeError, ValueError):
            continue
        if strategy:
            clean_candidates.append(
                {
                    "strategy": strategy,
                    "expected_equation_delta": delta,
                    "rationale_recorded": bool(rationale),
                }
            )
    deltas = [int(candidate["expected_equation_delta"]) for candidate in clean_candidates]
    return json.dumps(
        {
            "diagnostic_only": True,
            "patch_generated": False,
            "candidate_selected": False,
            "submitted": False,
            "compiler_named_residual_count": int(compiler_named_residual_count),
            "candidate_count": len(clean_candidates),
            "distinct_delta_count": len(set(deltas)),
            "expected_equation_deltas": deltas,
            "has_residual_matching_delta": int(compiler_named_residual_count) in set(deltas),
            "selected_strategy_recorded": bool(str(selected_strategy or "").strip()),
            "candidates": clean_candidates,
            "interpretation": [
                "This records the LLM's candidate space only; it does not generate Modelica code.",
                "A residual-matching delta is a coverage signal, not a selected repair.",
                "The LLM must still choose, write, test, and submit any candidate itself.",
            ],
        },
        sort_keys=True,
    )


def get_equation_delta_portfolio_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_equation_delta_portfolio_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "record_equation_delta_candidate_portfolio":
        return json.dumps({"error": f"unknown_equation_delta_portfolio_tool:{name}"}, sort_keys=True)
    try:
        residual_count = int(arguments.get("compiler_named_residual_count"))
    except (TypeError, ValueError):
        return json.dumps({"error": "compiler_named_residual_count_must_be_integer"}, sort_keys=True)
    candidates = arguments.get("candidates") if isinstance(arguments.get("candidates"), list) else []
    selected_strategy = str(arguments.get("selected_strategy") or "")
    if not candidates or not selected_strategy.strip():
        return json.dumps({"error": "candidates_and_selected_strategy_required"}, sort_keys=True)
    return record_equation_delta_candidate_portfolio(
        compiler_named_residual_count=residual_count,
        candidates=candidates,
        selected_strategy=selected_strategy,
    )
