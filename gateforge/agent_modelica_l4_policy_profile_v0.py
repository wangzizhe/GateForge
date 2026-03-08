from __future__ import annotations

import copy


SCHEMA_VERSION = "agent_modelica_l4_policy_profile_v0"
DEFAULT_POLICY_PROFILE = "score_v1"

_PROFILE_PRESETS = {
    "score_v1": {
        "score_weights": {
            "phase": 1000.0,
            "stage": 220.0,
            "subtype": 140.0,
            "memory": 8.0,
            "retrieval": 20.0,
            "retry_penalty": 80.0,
            "diversity": 8.0,
        },
        "memory_terms": {
            "success_scale": 20.0,
            "infra_risk_scale": 12.0,
            "round_penalty": 1.5,
        },
        "defaults": {
            "llm_fallback_threshold": 2,
        },
    },
    "score_v1a": {
        "score_weights": {
            "phase": 1000.0,
            "stage": 240.0,
            "subtype": 150.0,
            "memory": 9.0,
            "retrieval": 22.0,
            "retry_penalty": 84.0,
            "diversity": 9.0,
        },
        "memory_terms": {
            "success_scale": 21.0,
            "infra_risk_scale": 12.0,
            "round_penalty": 1.45,
        },
        "defaults": {
            "llm_fallback_threshold": 2,
        },
    },
    "score_v1b": {
        "score_weights": {
            "phase": 1000.0,
            "stage": 260.0,
            "subtype": 155.0,
            "memory": 9.5,
            "retrieval": 24.0,
            "retry_penalty": 92.0,
            "diversity": 9.0,
        },
        "memory_terms": {
            "success_scale": 22.0,
            "infra_risk_scale": 12.5,
            "round_penalty": 1.4,
        },
        "defaults": {
            "llm_fallback_threshold": 2,
        },
    },
    "score_v1c": {
        "score_weights": {
            "phase": 1000.0,
            "stage": 280.0,
            "subtype": 165.0,
            "memory": 10.0,
            "retrieval": 26.0,
            "retry_penalty": 96.0,
            "diversity": 9.5,
        },
        "memory_terms": {
            "success_scale": 23.0,
            "infra_risk_scale": 13.0,
            "round_penalty": 1.35,
        },
        "defaults": {
            "llm_fallback_threshold": 2,
        },
    },
}


def list_l4_policy_profiles_v0() -> list[str]:
    return sorted(_PROFILE_PRESETS.keys())


def resolve_l4_policy_profile_v0(profile_name: str | None) -> dict:
    requested = str(profile_name or "").strip().lower() or DEFAULT_POLICY_PROFILE
    resolved = requested if requested in _PROFILE_PRESETS else DEFAULT_POLICY_PROFILE
    preset = copy.deepcopy(_PROFILE_PRESETS[resolved])
    weights = preset.get("score_weights") if isinstance(preset.get("score_weights"), dict) else {}
    constraints = {
        "stage_ge_subtype": float(weights.get("stage", 0.0)) >= float(weights.get("subtype", 0.0)),
        "subtype_ge_memory": float(weights.get("subtype", 0.0)) >= float(weights.get("memory", 0.0)),
        "memory_ge_diversity": float(weights.get("memory", 0.0)) >= float(weights.get("diversity", 0.0)),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "requested_profile": requested,
        "resolved_profile": resolved,
        "fallback_used": requested != resolved,
        "score_weights": weights,
        "memory_terms": preset.get("memory_terms") if isinstance(preset.get("memory_terms"), dict) else {},
        "defaults": preset.get("defaults") if isinstance(preset.get("defaults"), dict) else {},
        "priority_constraints": constraints,
    }
