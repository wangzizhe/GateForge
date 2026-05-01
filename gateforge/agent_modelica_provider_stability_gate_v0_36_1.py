from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "provider_stability_gate_v0_36_1"

TRANSIENT_ERROR_MARKERS = (
    "service_unavailable",
    "timeout",
    "rate_limited",
    "overloaded",
    "temporarily_unavailable",
    "503",
    "502",
    "504",
)
BLOCKED_ERROR_MARKERS = (
    "unauthorized",
    "forbidden",
    "permission",
    "invalid_api_key",
    "api_key",
    "quota",
    "billing",
    "403",
    "401",
)
UNSUPPORTED_TOOL_MARKERS = (
    "unsupported_tool",
    "tool_use_unsupported",
    "function_call_unsupported",
    "tools_not_supported",
    "tool calls are not supported",
)


def classify_provider_status(
    *,
    provider: str,
    model: str,
    tool_profile: str,
    provider_errors: list[str] | None = None,
    tool_use_supported: bool = True,
) -> dict[str, Any]:
    errors = [str(error) for error in provider_errors or [] if str(error).strip()]
    joined = "\n".join(errors).lower()
    if not tool_use_supported or any(marker in joined for marker in UNSUPPORTED_TOOL_MARKERS):
        status = "provider_unsupported_tool_use"
    elif any(marker in joined for marker in BLOCKED_ERROR_MARKERS):
        status = "provider_blocked"
    elif any(marker in joined for marker in TRANSIENT_ERROR_MARKERS):
        status = "provider_unstable"
    elif errors:
        status = "provider_unstable"
    else:
        status = "provider_stable"
    return {
        "version": "v0.36.1",
        "analysis_scope": "provider_stability_gate",
        "provider": provider,
        "model": model,
        "tool_profile": tool_profile,
        "provider_status": status,
        "provider_error_count": len(errors),
        "provider_errors": errors,
        "tool_use_supported": bool(tool_use_supported),
        "conclusion_allowed": status == "provider_stable",
    }


def summarize_provider_smoke(results: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [str(row.get("provider_status") or "") for row in results]
    blocked = [status for status in statuses if status != "provider_stable"]
    return {
        "version": "v0.36.1",
        "analysis_scope": "provider_stability_smoke_summary",
        "status": "PASS" if not blocked else "REVIEW",
        "provider_status": "provider_stable" if not blocked else "provider_unstable",
        "conclusion_allowed": not blocked,
        "result_count": len(results),
        "blocked_result_count": len(blocked),
        "results": results,
    }


def write_provider_stability_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

