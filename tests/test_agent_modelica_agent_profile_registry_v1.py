from __future__ import annotations

import unittest

from gateforge.agent_modelica_agent_profile_registry_v1 import (
    get_agent_profile,
    list_agent_profiles,
)


class AgentModelicaAgentProfileRegistryV1Tests(unittest.TestCase):
    def test_get_repair_executor_profile(self) -> None:
        profile = get_agent_profile("repair-executor")
        self.assertEqual(profile.profile_id, "repair-executor")
        self.assertTrue(profile.source_restore_allowed)
        self.assertTrue(profile.deterministic_rules_enabled)
        self.assertIn("planner", profile.allowed_tool_families)

    def test_get_evidence_verifier_profile(self) -> None:
        profile = get_agent_profile("evidence-verifier")
        self.assertEqual(profile.profile_id, "evidence-verifier")
        self.assertFalse(profile.source_restore_allowed)
        self.assertTrue(profile.behavioral_contract_required)
        self.assertIn("classifier", profile.allowed_tool_families)

    def test_list_profiles_contains_two_minimal_profiles(self) -> None:
        profiles = list_agent_profiles()
        ids = {profile.profile_id for profile in profiles}
        self.assertEqual(ids, {"repair-executor", "evidence-verifier"})

    def test_unknown_profile_raises(self) -> None:
        with self.assertRaises(KeyError):
            get_agent_profile("unknown-profile")
