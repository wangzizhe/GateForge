import unittest

from gateforge.agent_modelica_action_applier_v0 import apply_repair_actions_to_modelica_v0


def _sample_modelica() -> str:
    return "\n".join(
        [
            "model A1",
            "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10);",
            "  Modelica.Electrical.Analog.Basic.Ground G1;",
            "equation",
            "  connect(R1.n, G1.p);",
            "end A1;",
            "",
        ]
    )


class AgentModelicaActionApplierV0Tests(unittest.TestCase):
    def test_apply_set_parameter_passes(self) -> None:
        result = apply_repair_actions_to_modelica_v0(
            modelica_text=_sample_modelica(),
            actions_payload=[
                {
                    "action_id": "a1",
                    "op": "set_parameter",
                    "target": {"component_id": "R1", "parameter": "R"},
                    "args": {"value": 22.0},
                    "reason_tag": "parameter_repair",
                    "source": "rule",
                    "confidence": 0.9,
                }
            ],
            max_actions_per_round=3,
        )
        self.assertEqual(result.get("status"), "PASS")
        updated_text = str(result.get("updated_modelica_text") or "")
        self.assertIn("R1(R=22.0)", updated_text)
        self.assertEqual(len(result.get("applied_actions") or []), 1)

    def test_apply_rolls_back_when_second_action_fails(self) -> None:
        result = apply_repair_actions_to_modelica_v0(
            modelica_text=_sample_modelica(),
            actions_payload=[
                {
                    "action_id": "a1",
                    "op": "set_parameter",
                    "target": {"component_id": "R1", "parameter": "R"},
                    "args": {"value": 33.0},
                    "reason_tag": "parameter_repair",
                    "source": "rule",
                    "confidence": 0.9,
                },
                {
                    "action_id": "a2",
                    "op": "disconnect_ports",
                    "target": {"from": "R1.p", "to": "G1.p"},
                    "args": {},
                    "reason_tag": "connector_repair",
                    "source": "rule",
                    "confidence": 0.8,
                },
            ],
            max_actions_per_round=3,
        )
        self.assertEqual(result.get("status"), "FAIL")
        self.assertTrue(bool(result.get("rolled_back")))
        self.assertEqual(result.get("apply_error_code"), "apply_error_connection_not_found")
        self.assertEqual(result.get("applied_actions"), [])

    def test_apply_rejects_non_whitelisted_new_type(self) -> None:
        result = apply_repair_actions_to_modelica_v0(
            modelica_text=_sample_modelica(),
            actions_payload=[
                {
                    "action_id": "a1",
                    "op": "replace_component",
                    "target": {"component_id": "R1"},
                    "args": {"new_type": "Foo.Bar.CustomComponent"},
                    "reason_tag": "component_replace",
                    "source": "rule",
                    "confidence": 0.7,
                }
            ],
            max_actions_per_round=3,
        )
        self.assertEqual(result.get("status"), "FAIL")
        self.assertEqual(result.get("apply_error_code"), "action_batch_invalid")

    def test_apply_connect_ports_accepts_underconstrained_probe_mutant_model(self) -> None:
        modelica = "\n".join(
            [
                "model A1",
                "  Modelica.Electrical.Analog.Sources.ConstantVoltage V1(V=10);",
                "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10);",
                "  Modelica.Electrical.Analog.Basic.Ground G1;",
                "  Real gateforge_underconstrained_probe_ab12cd34_a;",
                "  Real gateforge_underconstrained_probe_ab12cd34_b;",
                "equation",
                "  connect(R1.n, G1.p);",
                "  connect(V1.n, G1.p);",
                "  gateforge_underconstrained_probe_ab12cd34_a = gateforge_underconstrained_probe_ab12cd34_b;",
                "end A1;",
                "",
            ]
        )
        result = apply_repair_actions_to_modelica_v0(
            modelica_text=modelica,
            actions_payload=[
                {
                    "action_id": "a1",
                    "op": "connect_ports",
                    "target": {"from": "V1.p", "to": "R1.p"},
                    "args": {},
                    "reason_tag": "topology_restore",
                    "source": "rule",
                    "confidence": 0.98,
                }
            ],
            max_actions_per_round=3,
        )
        self.assertEqual(result.get("status"), "PASS")
        updated_text = str(result.get("updated_modelica_text") or "")
        self.assertIn("connect(V1.p, R1.p);", updated_text)
        self.assertEqual(len(result.get("applied_actions") or []), 1)


if __name__ == "__main__":
    unittest.main()
