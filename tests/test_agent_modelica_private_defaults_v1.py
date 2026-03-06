import unittest

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
        self.assertEqual(
            agent_modelica_landscape_snapshot_v1._default_hardpack_path(),
            "benchmarks/private/agent_modelica_hardpack_v1.json",
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
