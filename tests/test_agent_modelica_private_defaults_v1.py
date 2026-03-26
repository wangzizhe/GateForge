import unittest
from pathlib import Path

from gateforge import agent_modelica_hardpack_lock_v1
from gateforge import agent_modelica_landscape_snapshot_v1
from gateforge import agent_modelica_learning_preflight_v1
from gateforge import physics_contract_v0


class AgentModelicaPrivateDefaultsV1Tests(unittest.TestCase):
    def test_profile_default_prefers_private_path(self) -> None:
        self.assertEqual(
            agent_modelica_learning_preflight_v1._default_profile_path(),
            "benchmarks/private/agent_modelica_mvp_repair_v1.json",
        )

    def test_hardpack_defaults_prefer_private_path(self) -> None:
        expected_hardpack = "benchmarks/agent_modelica_hardpack_v1.json"
        frozen = Path("assets_private/agent_modelica_track_a_valid32_fixture_v1/hardpack_frozen.json")
        if frozen.exists():
            expected_hardpack = str(frozen)
        elif Path("benchmarks/private/agent_modelica_hardpack_v1.json").exists():
            expected_hardpack = "benchmarks/private/agent_modelica_hardpack_v1.json"
        self.assertEqual(
            agent_modelica_landscape_snapshot_v1._default_hardpack_path(),
            expected_hardpack,
        )
        self.assertEqual(
            agent_modelica_hardpack_lock_v1._default_hardpack_out_path(),
            "benchmarks/private/agent_modelica_hardpack_v1.json",
        )

    def test_physics_contract_default_prefers_private_path(self) -> None:
        self.assertEqual(
            physics_contract_v0.DEFAULT_PHYSICS_CONTRACT_PATH,
            "policies/private/physics_contract_v0.json",
        )


if __name__ == "__main__":
    unittest.main()
