from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_observation_contract_v0_26_1 import (
    OBSERVATION_CONTRACT_VERSION,
    build_observation_contract_summary,
    build_observation_event,
    observation_contract_schema,
    validate_observation_event,
)


class ObservationContractV0261Tests(unittest.TestCase):
    def test_valid_observation_event_passes(self) -> None:
        event = build_observation_event(
            run_id="r1",
            case_id="c1",
            repair_round_index=1,
            model_text="model Demo end Demo;",
            workflow_goal="Repair the model.",
            raw_omc_feedback="model_check_error",
            provider_name="deepseek",
            model_profile="deepseek-v4-flash",
        )
        self.assertEqual(validate_observation_event(event), [])

    def test_forbidden_repair_hint_is_rejected(self) -> None:
        event = build_observation_event(
            run_id="r1",
            case_id="c1",
            repair_round_index=1,
            model_text="model Demo end Demo;",
            workflow_goal="Repair the model.",
        )
        event["repair_hint"] = "Change the missing equation."
        self.assertIn("forbidden:repair_hint", validate_observation_event(event))

    def test_schema_declares_provider_agnostic_boundary(self) -> None:
        schema = observation_contract_schema()
        self.assertEqual(schema["schema_version"], OBSERVATION_CONTRACT_VERSION)
        self.assertTrue(schema["provider_agnostic"])
        self.assertFalse(schema["executor_decision_allowed"])
        self.assertIn("raw_omc_feedback", schema["required_fields"])

    def test_build_summary_writes_pass_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            summary = build_observation_contract_summary(out_dir=out_dir)
            self.assertEqual(summary["status"], "PASS")
            self.assertFalse(summary["observation_contains_hidden_hint"])
            self.assertTrue((out_dir / "schema.json").exists())
            self.assertTrue((out_dir / "canonical_event.json").exists())
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
