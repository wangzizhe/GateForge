"""Shared text-repair utility functions for the Modelica repair agent.

Extracted from agent_modelica_live_executor_gemini_v1.py to serve as a
leaf dependency for both the executor and the L4 guided search engine.
All functions are pure: they consume strings/dicts and return
strings/dicts, with no I/O, Docker, LLM, or OMC dependencies.
"""
from __future__ import annotations

import re


def find_primary_model_name(text: str) -> str:
    """Return the (possibly qualified) primary model/block/class name from *text*.

    Handles both standalone models (``model Foo``) and package-scoped definitions
    (``within A.B.C; block Foo``) by prepending the ``within`` path when present.
    Recognises ``model``, ``block``, ``class``, ``connector``, ``record``, and
    ``type`` top-level declarations.
    """
    src = str(text or "")
    # Extract optional "within X.Y.Z;" prefix
    within_prefix = ""
    within_m = re.search(r"(?im)^\s*within\s+([\w.]+)\s*;", src)
    if within_m:
        within_prefix = within_m.group(1).strip() + "."
    # Find first non-partial top-level declaration (model/block/class/etc.)
    decl_m = re.search(
        r"(?im)^\s*(?:partial\s+)?(?:model|block|class|connector|record|type)\s+([A-Za-z_]\w*)\b",
        src,
    )
    if not decl_m:
        return ""
    return within_prefix + str(decl_m.group(1))


def apply_regex_replacement_cluster(
    *,
    current_text: str,
    cluster_name: str,
    replacements: list[tuple[str, str]],
) -> tuple[str, dict]:
    """Apply a sequence of regex replacements and return *(patched_text, audit)*."""
    updated = str(current_text or "")
    applied_rules: list[dict] = []
    for pattern, replacement in replacements:
        candidate, count = re.subn(pattern, replacement, updated, count=1)
        if count > 0:
            updated = candidate
            applied_rules.append({"pattern": pattern, "replacement": replacement})
    if not applied_rules:
        return current_text, {"applied": False, "reason": f"{cluster_name}_not_applicable"}
    return updated, {
        "applied": True,
        "reason": f"source_blind_local_numeric_repair:{cluster_name}",
        "cluster_name": cluster_name,
        "rule_count": len(applied_rules),
        "rules": applied_rules,
    }


def format_numeric_candidate(value: float) -> str:
    """Format *value* as a compact numeric string."""
    if abs(value - int(value)) < 1e-9:
        return str(int(value))
    out = f"{value:.6f}".rstrip("0").rstrip(".")
    return out if out else "0"


def extract_named_numeric_values(
    *,
    current_text: str,
    names: list[str],
) -> dict[str, str]:
    """Extract current numeric assignments for *names* from Modelica *current_text*."""
    found: dict[str, str] = {}
    for name in names:
        match = re.search(rf"\b{re.escape(name)}\s*=\s*(-?\d+(?:\.\d+)?)\b", str(current_text or ""))
        if match:
            found[str(name)] = str(match.group(1))
    return found
