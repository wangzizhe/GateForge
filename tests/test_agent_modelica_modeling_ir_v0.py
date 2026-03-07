import unittest

from gateforge.agent_modelica_modeling_ir_v0 import (
    compare_ir_roundtrip,
    ir_to_modelica,
    modelica_to_ir,
    validate_ir,
)


def _sample_ir() -> dict:
    return {
        "schema_version": "modeling_ir_v0",
        "model_name": "SampleRC",
        "source_meta": {"domain": "electrical_analog", "task_id": "sample", "scale": "small"},
        "components": [
            {"id": "V1", "type": "Modelica.Electrical.Analog.Sources.ConstantVoltage", "params": {"V": 10.0}},
            {"id": "R1", "type": "Modelica.Electrical.Analog.Basic.Resistor", "params": {"R": 100.0}},
            {"id": "C1", "type": "Modelica.Electrical.Analog.Basic.Capacitor", "params": {"C": 0.01}},
            {"id": "VS1", "type": "Modelica.Electrical.Analog.Sensors.VoltageSensor", "params": {}},
            {"id": "G", "type": "Modelica.Electrical.Analog.Basic.Ground", "params": {}},
        ],
        "connections": [
            {"from": "V1.p", "to": "R1.p"},
            {"from": "R1.n", "to": "C1.p"},
            {"from": "C1.n", "to": "V1.n"},
            {"from": "V1.n", "to": "G.p"},
            {"from": "VS1.p", "to": "C1.p"},
            {"from": "VS1.n", "to": "G.p"},
        ],
        "structural_balance": {"variable_count": 5, "equation_count": 5},
        "simulation": {"start_time": 0.0, "stop_time": 1.0, "number_of_intervals": 500, "tolerance": 1e-6, "method": "dassl"},
        "validation_targets": ["VS1.v"],
    }


class AgentModelicaModelingIRV0Tests(unittest.TestCase):
    def test_validate_ir_accepts_valid_payload(self) -> None:
        ir = _sample_ir()
        ok, errors = validate_ir(ir)
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_validate_ir_rejects_missing_component_in_connection(self) -> None:
        ir = _sample_ir()
        ir["connections"] = [{"from": "V1.p", "to": "X9.p"}]
        ok, errors = validate_ir(ir)
        self.assertFalse(ok)
        self.assertTrue(any("connection_to_component_missing" in str(x) for x in errors))

    def test_validate_ir_rejects_unbalanced_variable_equation_counts(self) -> None:
        ir = _sample_ir()
        ir["structural_balance"] = {"variable_count": 6, "equation_count": 5}
        ok, errors = validate_ir(ir)
        self.assertFalse(ok)
        self.assertIn("structural_balance_not_square", errors)

    def test_ir_to_modelica_roundtrip_matches(self) -> None:
        ir = _sample_ir()
        mo = ir_to_modelica(ir)
        parsed = modelica_to_ir(mo)
        cmp = compare_ir_roundtrip(ir, parsed, ignore_source_meta=True)
        self.assertTrue(bool(cmp.get("match")), msg=str(cmp.get("diff_keys")))


if __name__ == "__main__":
    unittest.main()
