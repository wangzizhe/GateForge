from __future__ import annotations

from .agent_modelica_agent_profile_v1 import (
    SCHEMA_VERSION,
    AgentModelicaAgentProfile,
)


_REGISTRY: dict[str, AgentModelicaAgentProfile] = {
    "repair-executor": AgentModelicaAgentProfile(
        schema_version=SCHEMA_VERSION,
        profile_id="repair-executor",
        allowed_tool_families=("omc", "deterministic_rule", "planner", "guided_search", "verifier"),
        source_restore_allowed=True,
        deterministic_rules_enabled=True,
        replay_enabled=True,
        planner_injection_enabled=True,
        behavioral_contract_required=False,
        expected_output_schema="agent_modelica_run_contract_v1",
        artifact_write_policy="task_artifact_root",
    ),
    "evidence-verifier": AgentModelicaAgentProfile(
        schema_version=SCHEMA_VERSION,
        profile_id="evidence-verifier",
        allowed_tool_families=("omc", "verifier", "artifact_reader", "classifier"),
        source_restore_allowed=False,
        deterministic_rules_enabled=False,
        replay_enabled=False,
        planner_injection_enabled=False,
        behavioral_contract_required=True,
        expected_output_schema="agent_modelica_verification_contract_v1",
        artifact_write_policy="verification_artifact_root",
    ),
}


def get_agent_profile(profile_id: str) -> AgentModelicaAgentProfile:
    key = str(profile_id or "").strip()
    if key not in _REGISTRY:
        raise KeyError(f"Unknown agent profile: {profile_id}")
    return _REGISTRY[key]


def list_agent_profiles() -> list[AgentModelicaAgentProfile]:
    return list(_REGISTRY.values())
