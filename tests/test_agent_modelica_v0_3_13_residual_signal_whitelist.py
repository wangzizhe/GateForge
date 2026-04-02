from __future__ import annotations

import unittest

from gateforge.agent_modelica_v0_3_13_residual_signal_whitelist import (
    DEFAULT_SIGNAL_CLUSTERS,
    match_residual_signal_cluster,
)


class AgentModelicaV0313ResidualSignalWhitelistTests(unittest.TestCase):
    def test_matches_runtime_parameter_recovery_cluster(self) -> None:
        payload = {"clusters": DEFAULT_SIGNAL_CLUSTERS}
        diagnostic = {
            "stage_subtype": "stage_5_runtime_numerical_instability",
            "error_type": "numerical_instability",
            "reason": "division by zero",
        }

        matched = match_residual_signal_cluster(diagnostic=diagnostic, whitelist_payload=payload)

        self.assertEqual(matched.get("cluster_id"), "runtime_parameter_recovery")

    def test_returns_empty_for_unlisted_signal(self) -> None:
        payload = {"clusters": DEFAULT_SIGNAL_CLUSTERS}
        diagnostic = {
            "stage_subtype": "stage_3_behavioral_contract_semantic",
            "error_type": "constraint_violation",
            "reason": "assertion triggered",
        }

        matched = match_residual_signal_cluster(diagnostic=diagnostic, whitelist_payload=payload)

        self.assertEqual(matched, {})


if __name__ == "__main__":
    unittest.main()
