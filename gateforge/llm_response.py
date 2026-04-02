"""Shared LLM response parsing utilities.

Consolidates JSON extraction logic previously duplicated across
agent_modelica_live_executor_v1 and llm_planner.
"""

from __future__ import annotations

import json
import re


def extract_json_object(text: str, *, strict: bool = False) -> dict:
    """Extract a JSON object from LLM response text.

    Handles common LLM output quirks: markdown fences, extra whitespace,
    and partial JSON surrounded by non-JSON text.

    Args:
        text: Raw LLM response text.
        strict: If True, raise ValueError on parse failure.
                If False, return empty dict on failure.

    Returns:
        Parsed dict, or empty dict if parsing fails and strict is False.

    Raises:
        ValueError: If strict is True and no valid JSON object is found.
    """
    stripped = str(text or "").strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            if strict:
                raise ValueError("LLM response does not contain a JSON object")
            return {}
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            if strict:
                raise ValueError("LLM response contains malformed JSON")
            return {}
    if not isinstance(payload, dict):
        if strict:
            raise ValueError("LLM response JSON must be an object")
        return {}
    return payload
