from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import llm_provider_adapter


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "provider_profile_matrix_v0_26_2"

PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "gemini": {
        "transport_shape": "gemini_generate_content",
        "default_model_hint": "gemini",
        "response_extraction": "candidates[0].content.parts first non-thought text",
        "error_prefixes": ["gemini_rate_limited", "gemini_service_unavailable", "gemini_http_error"],
        "profile_controls": ["temperature", "responseMimeType"],
    },
    "openai": {
        "transport_shape": "openai_responses",
        "default_model_hint": "gpt",
        "response_extraction": "output_text or output[].content[].text",
        "error_prefixes": ["openai_rate_limited", "openai_service_unavailable", "openai_http_error"],
        "profile_controls": ["temperature"],
    },
    "qwen": {
        "transport_shape": "openai_compatible_responses",
        "default_model_hint": "qwen",
        "response_extraction": "output_text or output[].content[].text",
        "error_prefixes": ["qwen_rate_limited", "qwen_service_unavailable", "qwen_http_error"],
        "profile_controls": ["temperature", "enable_thinking", "thinking_budget", "prompt_prefix"],
    },
    "deepseek": {
        "transport_shape": "openai_compatible_chat_completions",
        "default_model_hint": "deepseek-v4-flash",
        "response_extraction": "choices[0].message.content",
        "error_prefixes": ["deepseek_rate_limited", "deepseek_service_unavailable", "deepseek_http_error"],
        "profile_controls": ["temperature", "max_tokens", "thinking", "response_format"],
    },
    "anthropic": {
        "transport_shape": "anthropic_messages",
        "default_model_hint": "claude",
        "response_extraction": "content[].text",
        "error_prefixes": ["anthropic_rate_limited", "anthropic_service_unavailable", "anthropic_http_error"],
        "profile_controls": ["temperature", "max_tokens"],
    },
    "minimax": {
        "transport_shape": "anthropic_compatible_messages",
        "default_model_hint": "MiniMax",
        "response_extraction": "content[].text",
        "error_prefixes": ["minimax_rate_limited", "minimax_service_unavailable", "minimax_http_error"],
        "profile_controls": ["temperature", "max_tokens", "system_prompt"],
    },
    "kimi": {
        "transport_shape": "openai_compatible_chat_completions",
        "default_model_hint": "kimi",
        "response_extraction": "choices[0].message.content",
        "error_prefixes": ["kimi_rate_limited", "kimi_service_unavailable", "kimi_http_error"],
        "profile_controls": ["temperature"],
    },
    "glm": {
        "transport_shape": "openai_compatible_chat_completions",
        "default_model_hint": "glm",
        "response_extraction": "choices[0].message.content",
        "error_prefixes": ["glm_rate_limited", "glm_service_unavailable", "glm_http_error"],
        "profile_controls": ["temperature"],
    },
}

DISALLOWED_PROFILE_CAPABILITIES = (
    "diagnose_modelica_error",
    "select_candidate",
    "rank_candidate",
    "generate_patch",
    "route_case",
    "deterministic_repair",
)


def build_provider_profile_matrix(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    registered_adapters = sorted(llm_provider_adapter._ADAPTERS.keys())  # type: ignore[attr-defined]
    profile_names = sorted(PROVIDER_PROFILES.keys())
    missing_registered_profiles = [name for name in registered_adapters if name not in PROVIDER_PROFILES]
    profile_without_adapter = [name for name in profile_names if name not in registered_adapters]
    disallowed_hits = {
        name: [
            term
            for term in DISALLOWED_PROFILE_CAPABILITIES
            if term in json.dumps(profile, sort_keys=True).lower()
        ]
        for name, profile in PROVIDER_PROFILES.items()
    }
    disallowed_hits = {name: hits for name, hits in disallowed_hits.items() if hits}
    ready = not missing_registered_profiles and not profile_without_adapter and not disallowed_hits
    summary = {
        "version": "v0.26.2",
        "status": "PASS" if ready else "REVIEW",
        "analysis_scope": "provider_adapter_model_profile_matrix",
        "registered_adapters": registered_adapters,
        "profile_names": profile_names,
        "provider_profiles": PROVIDER_PROFILES,
        "missing_registered_profiles": missing_registered_profiles,
        "profile_without_adapter": profile_without_adapter,
        "disallowed_profile_capability_hits": disallowed_hits,
        "matrix_policy": {
            "purpose": "request_output_stabilization_only",
            "multi_model_competition": False,
            "repair_strategy_changes_allowed": False,
            "candidate_selection_allowed": False,
            "provider_specific_executor_logic_allowed": False,
        },
        "decision": (
            "provider_profile_matrix_ready_for_run_mode_matrix"
            if ready
            else "provider_profile_matrix_needs_review"
        ),
        "next_focus": "v0.26.3_run_mode_matrix",
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "matrix.json").write_text(
        json.dumps(PROVIDER_PROFILES, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
