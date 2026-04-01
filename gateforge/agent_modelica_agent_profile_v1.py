from __future__ import annotations

from dataclasses import asdict, dataclass


SCHEMA_VERSION = "agent_modelica_agent_profile_v1"


@dataclass(frozen=True)
class AgentModelicaAgentProfile:
    schema_version: str
    profile_id: str
    allowed_tool_families: tuple[str, ...]
    source_restore_allowed: bool
    deterministic_rules_enabled: bool
    replay_enabled: bool
    planner_injection_enabled: bool
    behavioral_contract_required: bool
    expected_output_schema: str
    artifact_write_policy: str

    def to_dict(self) -> dict:
        return asdict(self)
