import unittest

from gateforge.agent_modelica_l4_policy_profile_v0 import (
    DEFAULT_POLICY_PROFILE,
    list_l4_policy_profiles_v0,
    resolve_l4_policy_profile_v0,
)


class AgentModelicaL4PolicyProfileV0Tests(unittest.TestCase):
    def test_list_profiles_contains_score_v1_variants(self) -> None:
        profiles = list_l4_policy_profiles_v0()
        self.assertIn("score_v1", profiles)
        self.assertIn("score_v1a", profiles)
        self.assertIn("score_v1b", profiles)
        self.assertIn("score_v1c", profiles)

    def test_resolve_known_profile(self) -> None:
        payload = resolve_l4_policy_profile_v0("score_v1b")
        self.assertEqual(str(payload.get("resolved_profile") or ""), "score_v1b")
        self.assertFalse(bool(payload.get("fallback_used")))
        constraints = payload.get("priority_constraints") if isinstance(payload.get("priority_constraints"), dict) else {}
        self.assertTrue(bool(constraints.get("stage_ge_subtype")))
        self.assertTrue(bool(constraints.get("subtype_ge_memory")))
        self.assertTrue(bool(constraints.get("memory_ge_diversity")))

    def test_resolve_unknown_profile_falls_back_to_default(self) -> None:
        payload = resolve_l4_policy_profile_v0("score_unknown_x")
        self.assertEqual(str(payload.get("resolved_profile") or ""), DEFAULT_POLICY_PROFILE)
        self.assertTrue(bool(payload.get("fallback_used")))


if __name__ == "__main__":
    unittest.main()
