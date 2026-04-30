from __future__ import annotations

import json
import re
from typing import Any

_DEFICIT_RE = re.compile(
    r"Class\s+\w+\s+has\s+(\d+)\s+equation\(s\)\s+and\s+(\d+)\s+variable\(s\)",
    re.IGNORECASE,
)

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "candidate_implementation_consistency_check",
        "description": (
            "Check whether a candidate model's implemented zero-flow equation count matches the LLM's expected "
            "equation delta AND whether that delta matches the OMC-reported deficit. "
            "Pass omc_output from the most recent check_model to enable deficit-aware verification. "
            "Audit-only; does not generate patches, select candidates, or submit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "candidate_model_text": {"type": "string"},
                "expected_equation_delta": {"type": "integer"},
                "candidate_strategy": {"type": "string"},
                "omc_output": {
                    "type": "string",
                    "description": "Raw OMC checkModel output for deficit comparison (optional but recommended).",
                },
            },
            "required": ["candidate_model_text", "expected_equation_delta", "candidate_strategy"],
        },
    }
]


def _zero_flow_equation_count(model_text: str) -> int:
    total = 0
    text = str(model_text or "")
    loop_pattern = re.compile(
        r"for\s+[A-Za-z_][A-Za-z0-9_]*\s+in\s+(\d+)\s*:\s*(\d+)\s+loop(?P<body>.*?)end\s+for\s*;",
        re.DOTALL,
    )
    loop_spans: list[tuple[int, int]] = []
    for loop in loop_pattern.finditer(text):
        start = int(loop.group(1))
        stop = int(loop.group(2))
        multiplier = max(0, stop - start + 1)
        total += multiplier * _zero_flow_equation_count(loop.group("body"))
        loop_spans.append(loop.span())
    remaining: list[str] = []
    cursor = 0
    for start, stop in loop_spans:
        remaining.append(text[cursor:start])
        cursor = stop
    remaining.append(text[cursor:])
    for row in "".join(remaining).split(";"):
        normalized = " ".join(row.strip().split())
        if re.search(r"\b[A-Za-z_][A-Za-z0-9_\[\]]*\.i\s*=\s*0(?:\.0)?$", normalized):
            total += 1
    return total


def _extract_deficit(omc_output: str) -> int | None:
    text = str(omc_output or "")
    m = _DEFICIT_RE.search(text)
    if not m:
        return None
    try:
        eq_count = int(m.group(1))
        var_count = int(m.group(2))
        return var_count - eq_count
    except (ValueError, IndexError):
        return None


def candidate_implementation_consistency_check(
    *,
    candidate_model_text: str,
    expected_equation_delta: int,
    candidate_strategy: str,
    omc_output: str = "",
) -> str:
    implemented_delta = _zero_flow_equation_count(candidate_model_text)
    implementation_matches = implemented_delta == int(expected_equation_delta)

    reported_deficit = _extract_deficit(omc_output)
    deficit_matches = None if reported_deficit is None else (expected_equation_delta == reported_deficit)

    result: dict[str, Any] = {
        "diagnostic_only": True,
        "patch_generated": False,
        "candidate_selected": False,
        "submitted": False,
        "candidate_strategy_recorded": bool(str(candidate_strategy or "").strip()),
        "expected_equation_delta": int(expected_equation_delta),
        "implemented_zero_flow_equation_count": implemented_delta,
        "implementation_matches_expected_delta": implementation_matches,
    }

    interpretation: list[str] = [
        "Implementation check: verifies the candidate text actually contains the claimed number of zero-flow equations.",
    ]

    if reported_deficit is not None:
        result["omc_reported_deficit"] = reported_deficit
        result["deficit_matches_expected_delta"] = deficit_matches
        if deficit_matches is True:
            interpretation.append(
                f"Deficit check PASSED: expected delta ({expected_equation_delta}) matches OMC deficit ({reported_deficit}). "
                "Your fix should close the equation gap exactly."
            )
        elif deficit_matches is False:
            interpretation.append(
                f"Deficit check FAILED: expected delta ({expected_equation_delta}) does NOT match OMC deficit ({reported_deficit}). "
                f"Your fix will result in a {'over' if expected_equation_delta > reported_deficit else 'under'}-determined system. "
                "Revise your hypothesis — the equation count you propose does not match what OMC reports."
            )
    else:
        result["omc_reported_deficit"] = None
        result["deficit_matches_expected_delta"] = None
        interpretation.append(
            "Deficit check skipped: no OMC output provided. Pass omc_output from recent check_model for deficit-aware verification."
        )

    interpretation.append(
        "This tool does not generate patches, select candidates, or submit. Revise and retest yourself."
    )
    result["interpretation"] = interpretation

    return json.dumps(result, sort_keys=True)


def get_candidate_implementation_consistency_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_candidate_implementation_consistency_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "candidate_implementation_consistency_check":
        return json.dumps({"error": f"unknown_candidate_implementation_consistency_tool:{name}"}, sort_keys=True)
    try:
        expected_delta = int(arguments.get("expected_equation_delta"))
    except (TypeError, ValueError):
        return json.dumps({"error": "expected_equation_delta_must_be_integer"}, sort_keys=True)
    model_text = str(arguments.get("candidate_model_text") or "")
    strategy = str(arguments.get("candidate_strategy") or "")
    if not model_text.strip() or not strategy.strip():
        return json.dumps({"error": "candidate_model_text_and_strategy_required"}, sort_keys=True)
    return candidate_implementation_consistency_check(
        candidate_model_text=model_text,
        expected_equation_delta=expected_delta,
        candidate_strategy=strategy,
        omc_output=str(arguments.get("omc_output") or ""),
    )
