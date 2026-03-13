import unittest

from gateforge.agent_modelica_l4_orchestrator_v0 import (
    _build_rule_action_from_text,
    run_l4_orchestrator_v0,
)


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


class AgentModelicaL4OrchestratorV0Tests(unittest.TestCase):
    def test_rule_action_uses_sorted_param_name_when_semantics_returns_set(self) -> None:
        ir_payload = {
            "schema_version": "modeling_ir_v0",
            "model_name": "A1",
            "components": [
                {
                    "id": "V1",
                    "type": "Modelica.Electrical.Analog.Sources.ConstantVoltage",
                    "params": {},
                }
            ],
            "connections": [],
            "structural_balance": {"variable_count": 1, "equation_count": 1},
            "simulation": {
                "start_time": 0.0,
                "stop_time": 1.0,
                "number_of_intervals": 100,
                "tolerance": 1e-6,
                "method": "dassl",
            },
        }
        action = _build_rule_action_from_text(
            action_id="a1",
            action_text="adjust parameter value to fix issue",
            ir_payload=ir_payload,
            source="rule",
            confidence=0.5,
        )
        self.assertIsInstance(action, dict)
        self.assertEqual(str(action.get("op") or ""), "set_parameter")
        target = action.get("target") if isinstance(action.get("target"), dict) else {}
        self.assertEqual(str(target.get("component_id") or ""), "V1")
        self.assertEqual(str(target.get("parameter") or ""), "V")

    def test_orchestrator_recovers_on_second_round(self) -> None:
        def _runner(round_idx: int, _model_text: str, _actions: list[str]) -> dict:
            if round_idx == 1:
                return {
                    "check_model_pass": False,
                    "simulate_pass": False,
                    "physics_contract_pass": False,
                    "regression_pass": False,
                    "elapsed_sec": 1.0,
                    "observed_failure_type": "model_check_error",
                    "reason": "compile/syntax error",
                    "stderr_snippet": "Error: undefined symbol",
                }
            return {
                "check_model_pass": True,
                "simulate_pass": True,
                "physics_contract_pass": True,
                "regression_pass": True,
                "elapsed_sec": 1.0,
                "observed_failure_type": "none",
                "reason": "",
            }

        result = run_l4_orchestrator_v0(
            task={"task_id": "t1", "failure_type": "model_check_error", "expected_stage": "check"},
            initial_model_text=_sample_modelica(),
            initial_actions=["resolve undefined symbols"],
            run_attempt=_runner,
            max_rounds=3,
            max_time_sec=30,
            max_actions_per_round=3,
        )
        self.assertEqual(result.get("status"), "PASS")
        self.assertEqual(int(result.get("rounds_used") or 0), 2)
        self.assertEqual(result.get("stop_reason"), "hard_checks_pass")
        self.assertEqual(str(result.get("l4_primary_reason") or ""), "hard_checks_pass")
        self.assertIn("llm_fallback_used", result)
        self.assertIsInstance(result.get("action_rank_trace"), list)
        self.assertGreaterEqual(len(result.get("trajectory_rows") or []), 1)

    def test_orchestrator_stops_on_no_progress_window(self) -> None:
        def _runner(_round_idx: int, _model_text: str, _actions: list[str]) -> dict:
            return {
                "check_model_pass": False,
                "simulate_pass": False,
                "physics_contract_pass": False,
                "regression_pass": False,
                "elapsed_sec": 1.0,
                "observed_failure_type": "model_check_error",
                "reason": "compile/syntax error",
                "stderr_snippet": "Error: undefined symbol",
            }

        result = run_l4_orchestrator_v0(
            task={"task_id": "t2", "failure_type": "model_check_error", "expected_stage": "check"},
            initial_model_text=_sample_modelica(),
            initial_actions=["resolve undefined symbols"],
            run_attempt=_runner,
            max_rounds=5,
            max_time_sec=60,
            no_progress_window=2,
        )
        self.assertEqual(result.get("status"), "FAIL")
        self.assertEqual(result.get("stop_reason"), "no_progress_window")
        self.assertGreaterEqual(int(result.get("rounds_used") or 0), 3)
        self.assertEqual(str(result.get("l4_primary_reason") or ""), "no_progress_window")
        self.assertGreaterEqual(len(result.get("action_rank_trace") or []), 1)
        self.assertGreaterEqual(len(result.get("banned_action_signatures") or []), 1)

    def test_orchestrator_stops_on_time_budget(self) -> None:
        def _runner(_round_idx: int, _model_text: str, _actions: list[str]) -> dict:
            return {
                "check_model_pass": False,
                "simulate_pass": False,
                "physics_contract_pass": False,
                "regression_pass": False,
                "elapsed_sec": 10.0,
                "observed_failure_type": "simulate_error",
                "reason": "simulation timeout",
                "stderr_snippet": "TimeoutExpired",
            }

        result = run_l4_orchestrator_v0(
            task={"task_id": "t3", "failure_type": "simulate_error", "expected_stage": "simulate"},
            initial_model_text=_sample_modelica(),
            initial_actions=["stabilize initialization"],
            run_attempt=_runner,
            max_rounds=3,
            max_time_sec=5,
        )
        self.assertEqual(result.get("status"), "FAIL")
        self.assertEqual(result.get("stop_reason"), "time_budget_exceeded")
        self.assertEqual(str(result.get("l4_primary_reason") or ""), "time_budget_exceeded")

    def test_orchestrator_unknown_policy_profile_falls_back(self) -> None:
        def _runner(_round_idx: int, _model_text: str, _actions: list[str]) -> dict:
            return {
                "check_model_pass": False,
                "simulate_pass": False,
                "physics_contract_pass": False,
                "regression_pass": False,
                "elapsed_sec": 1.0,
                "observed_failure_type": "model_check_error",
                "reason": "compile/syntax error",
                "stderr_snippet": "Error: undefined symbol",
            }

        result = run_l4_orchestrator_v0(
            task={"task_id": "t4", "failure_type": "model_check_error", "expected_stage": "check"},
            initial_model_text=_sample_modelica(),
            initial_actions=["resolve undefined symbols"],
            run_attempt=_runner,
            max_rounds=1,
            max_time_sec=30,
            policy_profile="unknown_profile_x",
        )
        self.assertEqual(str(result.get("policy_profile") or ""), "unknown_profile_x")
        ranks = result.get("action_rank_trace") if isinstance(result.get("action_rank_trace"), list) else []
        self.assertGreaterEqual(len(ranks), 1)
        first = ranks[0] if isinstance(ranks[0], dict) else {}
        self.assertEqual(str(first.get("policy_profile") or ""), "score_v1")

    def test_orchestrator_underconstrained_uses_exact_removed_edge_restore(self) -> None:
        def _runner(round_idx: int, _model_text: str, _actions: list[str]) -> dict:
            if round_idx == 1:
                return {
                    "check_model_pass": False,
                    "simulate_pass": False,
                    "physics_contract_pass": False,
                    "regression_pass": False,
                    "elapsed_sec": 1.0,
                    "observed_failure_type": "model_check_error",
                    "reason": "Class A1 has 3 equation(s) and 4 variable(s). gateforge_underconstrained_probe_ab12cd34",
                    "stderr_snippet": "structural_underconstraint dangling_connectivity",
                }
            return {
                "check_model_pass": True,
                "simulate_pass": True,
                "physics_contract_pass": True,
                "regression_pass": True,
                "elapsed_sec": 1.0,
                "observed_failure_type": "none",
                "reason": "",
            }

        result = run_l4_orchestrator_v0(
            task={
                "task_id": "t_under",
                "failure_type": "underconstrained_system",
                "expected_stage": "check",
                "mutated_objects": [
                    {
                        "kind": "connection_edge",
                        "removed_from": "R1.p",
                        "removed_to": "G1.p",
                        "effect": "dangling_connectivity",
                    }
                ],
            },
            initial_model_text=_sample_modelica(),
            initial_actions=["restore dropped connect path and dangling conservation balance before equation rewrites"],
            run_attempt=_runner,
            max_rounds=2,
            max_time_sec=30,
            max_actions_per_round=3,
        )
        self.assertEqual(result.get("status"), "PASS")
        attempts = result.get("attempts") if isinstance(result.get("attempts"), list) else []
        first = attempts[0] if attempts and isinstance(attempts[0], dict) else {}
        l4 = first.get("l4") if isinstance(first.get("l4"), dict) else {}
        planned = l4.get("planned_actions") if isinstance(l4.get("planned_actions"), list) else []
        self.assertEqual(len(planned), 1)
        action = planned[0] if planned and isinstance(planned[0], dict) else {}
        self.assertEqual(str(action.get("op") or ""), "connect_ports")
        target = action.get("target") if isinstance(action.get("target"), dict) else {}
        self.assertEqual(str(target.get("from") or ""), "R1.p")
        self.assertEqual(str(target.get("to") or ""), "G1.p")
        self.assertEqual(str(action.get("reason_tag") or ""), "topology_restore")

    def test_orchestrator_connector_mismatch_uses_exact_endpoint_rewrite(self) -> None:
        def _runner(round_idx: int, _model_text: str, _actions: list[str]) -> dict:
            if round_idx == 1:
                return {
                    "check_model_pass": False,
                    "simulate_pass": False,
                    "physics_contract_pass": False,
                    "regression_pass": False,
                    "elapsed_sec": 1.0,
                    "observed_failure_type": "model_check_error",
                    "reason": "Error: Variable R1.badPort not found in scope A1.",
                    "stderr_snippet": "undefined symbol R1.badPort",
                }
            return {
                "check_model_pass": True,
                "simulate_pass": True,
                "physics_contract_pass": True,
                "regression_pass": True,
                "elapsed_sec": 1.0,
                "observed_failure_type": "none",
                "reason": "",
            }

        modelica = "\n".join(
            [
                "model A1",
                "  Modelica.Electrical.Analog.Sources.ConstantVoltage V1(V=10);",
                "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10);",
                "  Modelica.Electrical.Analog.Basic.Ground G1;",
                "equation",
                "  connect(V1.p, R1.badPort);",
                "  connect(R1.n, G1.p);",
                "  connect(V1.n, G1.p);",
                "end A1;",
                "",
            ]
        )
        result = run_l4_orchestrator_v0(
            task={
                "task_id": "t_conn",
                "failure_type": "connector_mismatch",
                "expected_stage": "check",
                "mutated_objects": [
                    {
                        "kind": "connection_endpoint",
                        "from": "V1.p",
                        "to_before": "R1.p",
                        "to_after": "R1.badPort",
                    }
                ],
            },
            initial_model_text=modelica,
            initial_actions=["align connector types and endpoint port names"],
            run_attempt=_runner,
            max_rounds=2,
            max_time_sec=30,
            max_actions_per_round=3,
        )
        self.assertEqual(result.get("status"), "PASS")
        attempts = result.get("attempts") if isinstance(result.get("attempts"), list) else []
        first = attempts[0] if attempts and isinstance(attempts[0], dict) else {}
        l4 = first.get("l4") if isinstance(first.get("l4"), dict) else {}
        planned = l4.get("planned_actions") if isinstance(l4.get("planned_actions"), list) else []
        self.assertEqual(len(planned), 1)
        action = planned[0] if planned and isinstance(planned[0], dict) else {}
        self.assertEqual(str(action.get("op") or ""), "rewrite_connection_endpoint")
        target = action.get("target") if isinstance(action.get("target"), dict) else {}
        self.assertEqual(str(target.get("from") or ""), "V1.p")
        self.assertEqual(str(target.get("to_before") or ""), "R1.badPort")
        self.assertEqual(str(target.get("to_after") or ""), "R1.p")


if __name__ == "__main__":
    unittest.main()
