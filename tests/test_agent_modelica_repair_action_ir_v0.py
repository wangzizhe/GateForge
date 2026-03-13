import unittest

from gateforge.agent_modelica_repair_action_ir_v0 import validate_action_batch_v0


def _sample_ir() -> dict:
    return {
        "schema_version": "modeling_ir_v0",
        "model_name": "A1",
        "source_meta": {},
        "components": [
            {
                "id": "R1",
                "type": "Modelica.Electrical.Analog.Basic.Resistor",
                "params": {"R": 10.0},
            },
            {
                "id": "G1",
                "type": "Modelica.Electrical.Analog.Basic.Ground",
                "params": {},
            },
        ],
        "connections": [{"from": "R1.p", "to": "G1.p"}],
        "structural_balance": {"variable_count": 2, "equation_count": 2},
        "simulation": {
            "start_time": 0.0,
            "stop_time": 1.0,
            "number_of_intervals": 10,
            "tolerance": 1e-6,
            "method": "dassl",
        },
        "validation_targets": ["R1.p"],
    }


class AgentModelicaRepairActionIRV0Tests(unittest.TestCase):
    def test_validate_passes_for_whitelisted_action_batch(self) -> None:
        summary = validate_action_batch_v0(
            actions_payload=[
                {
                    "action_id": "a1",
                    "op": "set_parameter",
                    "target": {"component_id": "R1", "parameter": "R"},
                    "args": {"value": 12.5},
                    "reason_tag": "parameter_repair",
                    "source": "rule",
                    "confidence": 0.9,
                }
            ],
            ir_payload=_sample_ir(),
            max_actions_per_round=3,
        )
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(len(summary.get("normalized_actions") or []), 1)

    def test_validate_rejects_non_whitelisted_parameter(self) -> None:
        summary = validate_action_batch_v0(
            actions_payload=[
                {
                    "action_id": "a1",
                    "op": "set_parameter",
                    "target": {"component_id": "R1", "parameter": "NOT_ALLOWED"},
                    "args": {"value": 1.0},
                    "reason_tag": "parameter_repair",
                    "source": "rule",
                    "confidence": 0.8,
                }
            ],
            ir_payload=_sample_ir(),
            max_actions_per_round=3,
        )
        self.assertEqual(summary.get("status"), "FAIL")
        rejected = summary.get("rejected_actions") if isinstance(summary.get("rejected_actions"), list) else []
        self.assertTrue(rejected)
        first = rejected[0] if isinstance(rejected[0], dict) else {}
        self.assertIn("target_parameter_not_allowed", first.get("errors") or [])

    def test_validate_rejects_invalid_endpoint(self) -> None:
        summary = validate_action_batch_v0(
            actions_payload=[
                {
                    "action_id": "a1",
                    "op": "connect_ports",
                    "target": {"from": "R1.bad_port", "to": "G1.p"},
                    "args": {},
                    "reason_tag": "connector_repair",
                    "source": "rule",
                    "confidence": 0.7,
                }
            ],
            ir_payload=_sample_ir(),
            max_actions_per_round=3,
        )
        self.assertEqual(summary.get("status"), "FAIL")
        rejected = summary.get("rejected_actions") if isinstance(summary.get("rejected_actions"), list) else []
        self.assertTrue(rejected)
        first = rejected[0] if isinstance(rejected[0], dict) else {}
        self.assertIn("from_endpoint_port_invalid", first.get("errors") or [])

    def test_validate_enforces_max_actions_per_round(self) -> None:
        summary = validate_action_batch_v0(
            actions_payload=[
                {
                    "action_id": "a1",
                    "op": "set_parameter",
                    "target": {"component_id": "R1", "parameter": "R"},
                    "args": {"value": 11.0},
                    "reason_tag": "parameter_repair",
                    "source": "rule",
                    "confidence": 0.8,
                },
                {
                    "action_id": "a2",
                    "op": "replace_component",
                    "target": {"component_id": "R1"},
                    "args": {"new_type": "Modelica.Electrical.Analog.Basic.Capacitor"},
                    "reason_tag": "component_replace",
                    "source": "rule",
                    "confidence": 0.8,
                },
            ],
            ir_payload=_sample_ir(),
            max_actions_per_round=1,
        )
        self.assertEqual(summary.get("status"), "FAIL")
        self.assertIn("max_actions_per_round_exceeded", summary.get("errors") or [])

    def test_validate_passes_for_rewrite_connection_endpoint(self) -> None:
        summary = validate_action_batch_v0(
            actions_payload=[
                {
                    "action_id": "a1",
                    "op": "rewrite_connection_endpoint",
                    "target": {"from": "R1.p", "to_before": "G1.badPort", "to_after": "G1.p"},
                    "args": {},
                    "reason_tag": "connector_repair",
                    "source": "rule",
                    "confidence": 0.9,
                }
            ],
            ir_payload=_sample_ir(),
            max_actions_per_round=3,
        )
        self.assertEqual(summary.get("status"), "PASS")


if __name__ == "__main__":
    unittest.main()
