from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_workspace_style_probe_v0_67_0 import (
    _extract_omc_diagnostics,
    _extract_model_name,
)


class TwoPhaseRepairV068Tests(unittest.TestCase):
    def test_extract_diagnostics_parses_unconstrained_variables(self) -> None:
        output = (
            "true\n"
            "true\n"
            "Class M has 30 equation(s) and 34 variable(s).\n"
            "Variable probe[1].p.i does not have any remaining equation to be solved in.\n"
            "Variable probe[2].n.i does not have any remaining equation to be solved in.\n"
            'record SimulationResult resultFile = "",\n'
        )
        diags = _extract_omc_diagnostics(output)
        self.assertIn("unconstrained_variables", diags)
        self.assertEqual(len(diags["unconstrained_variables"]), 2)
        self.assertEqual(diags["simulation"], "NO_RESULT")

    def test_extract_diagnostics_parses_subsystem_imbalance(self) -> None:
        output = (
            'Class M has 42 equation(s) and 42 variable(s).\n'
            'An independent subset of the model has imbalanced number of equations (38) and variables (40).\n'
        )
        diags = _extract_omc_diagnostics(output)
        self.assertIn("subsystem_imbalance", diags)
        self.assertEqual(diags["subsystem_imbalance"]["equations"], 38)

    def test_extract_diagnostics_parses_simulation_ok(self) -> None:
        output = (
            'Class M has 38 equation(s) and 38 variable(s).\n'
            'The simulation finished successfully.\n'
        )
        diags = _extract_omc_diagnostics(output)
        self.assertEqual(diags["simulation"], "OK")


if __name__ == "__main__":
    unittest.main()
