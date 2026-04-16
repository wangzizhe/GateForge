from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

from gateforge.agent_modelica_semantic_time_constant_oracle_v1 import (
    TARGET_RESPONSE_FRACTION,
    _extract_contract_spec,
    _response_fraction,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_benchmark_gf_v1 import _normalise_semantic  # noqa: E402
from build_semantic_reasoning_mutations_v0_19_15 import SPECS, build_model_text  # noqa: E402


class V01915SemanticOracleTests(unittest.TestCase):
    def test_model_text_removes_legacy_contract_markers(self) -> None:
        text = build_model_text(SPECS[0], capacitor=SPECS[0].mutated_capacitor)

        self.assertNotIn("gateforge_semantic_contract_operands", text)
        self.assertNotIn("gateforge_semantic_contract_target", text)
        self.assertIn("gateforge_source_blind_multistep_llm_forcing:true", text)

    def test_contract_spec_uses_source_metadata(self) -> None:
        spec = _extract_contract_spec(build_model_text(SPECS[1], capacitor=SPECS[1].source_capacitor))

        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec["model_name"], "V01915SemanticRCStepTau05")
        self.assertEqual(spec["observation_var"], "VS1.v")
        self.assertAlmostEqual(spec["expected_tau"], 0.5)
        self.assertAlmostEqual(spec["event_time"], 0.05)

    def test_response_fraction_matches_one_tau_reference(self) -> None:
        times = [i / 20.0 for i in range(81)]
        values = [1.0 - math.exp(-t) for t in times]
        metrics = _response_fraction(
            data={"time": times, "VS1.v": values},
            observation_var="VS1.v",
            event_time=0.0,
            tau=1.0,
        )

        self.assertAlmostEqual(metrics["fraction"], TARGET_RESPONSE_FRACTION, delta=0.03)

    def test_benchmark_normalise_semantic_uses_behavioral_contract_fail(self) -> None:
        row = {
            "candidate_id": "case_a",
            "source_model_path": "/tmp/source.mo",
            "mutated_model_path": "/tmp/mutated.mo",
            "workflow_goal": "goal",
            "failure_type": "behavioral_contract_fail",
            "semantic_oracle": {"kind": "simulation_based_time_constant"},
        }

        normalized = _normalise_semantic(row)

        self.assertEqual(normalized["benchmark_family"], "semantic_time_constant")
        self.assertEqual(normalized["failure_type"], "behavioral_contract_fail")
        self.assertEqual(normalized["_source_version"], "v0.19.15")
        self.assertEqual(normalized["_semantic_oracle"]["kind"], "simulation_based_time_constant")


if __name__ == "__main__":
    unittest.main()
