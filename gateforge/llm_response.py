"""Shared LLM response parsing utilities.

Consolidates JSON extraction logic previously duplicated across
agent_modelica_live_executor_v1 and llm_planner.
"""

from __future__ import annotations

import json
import re


def _scan_json_objects(text: str) -> list[dict]:
    """Scan text for all balanced {...} blocks and return those that parse as dicts.

    Uses a character-level balanced-brace scan rather than greedy regex so that
    thinking-model responses (which wrap the answer in reasoning text) are handled
    correctly.  Returns candidates in document order; callers that want the 'last
    meaningful answer' should reverse-iterate.
    """
    results: list[dict] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        j = i
        in_string = False
        escape_next = False
        while j < n:
            ch = text[j]
            if escape_next:
                escape_next = False
            elif ch == "\\" and in_string:
                escape_next = True
            elif ch == '"':
                in_string = not in_string
            elif not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[i : j + 1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, dict):
                                results.append(parsed)
                        except json.JSONDecodeError:
                            pass
                        break
            j += 1
        i = j + 1
    return results


def extract_json_object(text: str, *, strict: bool = False) -> dict:
    """Extract a JSON object from LLM response text.

    Handles common LLM output quirks: markdown fences, extra whitespace,
    partial JSON surrounded by non-JSON text, and thinking-model responses
    where the answer JSON is embedded inside reasoning paragraphs.

    Strategy:
    1. Strip markdown fences.
    2. Try direct json.loads on the full text.
    3. Use balanced-brace scanning to find all valid JSON dicts; return the
       last one with more than one key (thinking models put the answer last).
    4. Fall back to the last single-key dict, or the first dict found.

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

    # Fast path: the whole text is already a JSON object.
    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    # Balanced-brace scan: handles thinking-model reasoning wrappers.
    candidates = _scan_json_objects(stripped)
    if candidates:
        # Prefer the last dict with >1 key (the final answer in a CoT response).
        multi_key = [c for c in candidates if len(c) > 1]
        chosen = multi_key[-1] if multi_key else candidates[-1]
        return chosen

    if strict:
        raise ValueError("LLM response does not contain a JSON object")
    return {}
