import unittest

from gateforge.agent_modelica_electrical_msl_semantics_v0 import (
    allowed_ir_param_names,
    is_valid_port,
    normalize_ir_params_for_modelica_emit,
    normalize_ir_params_for_validation,
    normalize_modelica_params_for_ir,
)


class AgentModelicaElectricalMslSemanticsV0Tests(unittest.TestCase):
    def test_allowed_ir_param_names_for_sine_voltage(self) -> None:
        names = allowed_ir_param_names("Modelica.Electrical.Analog.Sources.SineVoltage")
        self.assertIn("freqHz", names)
        self.assertIn("f", names)
        self.assertIn("frequency", names)

    def test_normalize_ir_params_for_validation_maps_alias(self) -> None:
        params, errors = normalize_ir_params_for_validation(
            "Modelica.Electrical.Analog.Sources.SineVoltage",
            {"V": 3.0, "f": 40.0},
        )
        self.assertEqual(errors, [])
        self.assertEqual(float(params["freqHz"]), 40.0)

    def test_normalize_ir_params_for_validation_detects_alias_conflict(self) -> None:
        params, errors = normalize_ir_params_for_validation(
            "Modelica.Electrical.Analog.Sources.SineVoltage",
            {"freqHz": 50.0, "f": 60.0},
        )
        self.assertIn("freqHz", params)
        self.assertTrue(any("param_alias_conflict" in x for x in errors))

    def test_normalize_ir_params_for_modelica_emit_uses_f(self) -> None:
        out = normalize_ir_params_for_modelica_emit(
            "Modelica.Electrical.Analog.Sources.SineVoltage",
            {"V": 3.0, "freqHz": 50.0},
        )
        self.assertIn("f", out)
        self.assertNotIn("freqHz", out)
        self.assertEqual(float(out["f"]), 50.0)

    def test_normalize_modelica_params_for_ir_maps_to_freqhz(self) -> None:
        out = normalize_modelica_params_for_ir(
            "Modelica.Electrical.Analog.Sources.SineVoltage",
            {"V": 3.0, "f": 50.0},
        )
        self.assertIn("freqHz", out)
        self.assertEqual(float(out["freqHz"]), 50.0)

    def test_is_valid_port_uses_signature(self) -> None:
        self.assertTrue(is_valid_port("Modelica.Electrical.Analog.Basic.Resistor", "p"))
        self.assertFalse(is_valid_port("Modelica.Electrical.Analog.Basic.Ground", "n"))


if __name__ == "__main__":
    unittest.main()
