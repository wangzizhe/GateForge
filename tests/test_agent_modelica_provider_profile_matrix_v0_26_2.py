from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_provider_profile_matrix_v0_26_2 import (
    PROVIDER_PROFILES,
    build_provider_profile_matrix,
)


class ProviderProfileMatrixV0262Tests(unittest.TestCase):
    def test_build_matrix_reports_complete_registered_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            summary = build_provider_profile_matrix(out_dir=out_dir)
            self.assertEqual(summary["status"], "PASS")
            self.assertIn("deepseek", summary["registered_adapters"])
            self.assertEqual(summary["missing_registered_profiles"], [])
            self.assertEqual(summary["profile_without_adapter"], [])
            self.assertTrue((out_dir / "matrix.json").exists())
            self.assertTrue((out_dir / "summary.json").exists())

    def test_deepseek_profile_is_transport_only(self) -> None:
        profile = PROVIDER_PROFILES["deepseek"]
        self.assertEqual(profile["transport_shape"], "openai_compatible_chat_completions")
        self.assertEqual(profile["response_extraction"], "choices[0].message.content")
        self.assertIn("deepseek_service_unavailable", profile["error_prefixes"])
        self.assertNotIn("select_candidate", str(profile))
        self.assertNotIn("generate_patch", str(profile))

    def test_matrix_policy_disallows_provider_specific_executor_logic(self) -> None:
        summary = build_provider_profile_matrix(out_dir=Path(tempfile.mkdtemp()) / "out")
        policy = summary["matrix_policy"]
        self.assertFalse(policy["multi_model_competition"])
        self.assertFalse(policy["repair_strategy_changes_allowed"])
        self.assertFalse(policy["candidate_selection_allowed"])
        self.assertFalse(policy["provider_specific_executor_logic_allowed"])


if __name__ == "__main__":
    unittest.main()
