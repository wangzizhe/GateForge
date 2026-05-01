from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "tool_profile_health_audit_v0_36_2"

DEFAULT_TOOL_PROFILES = [
    "base",
    "structural",
    "semantic",
    "connector",
    "connector_flow_state_checkpoint",
    "connector_flow_candidate_implementation_checkpoint",
]


def estimate_tool_profile_health(tool_profile: str) -> dict[str, Any]:
    tools = get_tool_defs(tool_profile)
    guidance = get_tool_profile_guidance(tool_profile)
    schema_chars = len(json.dumps(tools, sort_keys=True))
    guidance_chars = len(guidance)
    tool_count = len(tools)
    first_request_complexity = schema_chars + guidance_chars + tool_count * 250
    provider_sensitive = tool_count > 6 or schema_chars > 8000 or first_request_complexity > 10000
    lightweight_model_suitable = tool_count <= 5 and first_request_complexity <= 6500
    return {
        "profile": tool_profile,
        "tool_count": tool_count,
        "schema_chars": schema_chars,
        "guidance_chars": guidance_chars,
        "first_request_complexity": first_request_complexity,
        "provider_sensitive": provider_sensitive,
        "lightweight_model_suitable": lightweight_model_suitable,
        "status": "REVIEW" if provider_sensitive else "PASS",
    }


def build_tool_profile_health_summary(
    profiles: list[str] | None = None,
    *,
    version: str = "v0.36.2",
) -> dict[str, Any]:
    rows = [estimate_tool_profile_health(profile) for profile in (profiles or DEFAULT_TOOL_PROFILES)]
    sensitive = [row["profile"] for row in rows if row["provider_sensitive"]]
    return {
        "version": version,
        "analysis_scope": "tool_profile_health_audit",
        "status": "REVIEW" if sensitive else "PASS",
        "profile_count": len(rows),
        "provider_sensitive_profiles": sensitive,
        "profiles": rows,
        "discipline": {
            "auto_tool_pruning": False,
            "capability_claim_made": False,
        },
    }


def write_tool_profile_health_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

