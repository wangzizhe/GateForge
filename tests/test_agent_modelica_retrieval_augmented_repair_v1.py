import unittest

from gateforge.agent_modelica_retrieval_augmented_repair_v1 import retrieve_repair_examples


class AgentModelicaRetrievalAugmentedRepairV1Tests(unittest.TestCase):
    def test_retrieves_similar_success_rows(self) -> None:
        history = {
            "rows": [
                {
                    "failure_type": "simulate_error",
                    "model_id": "LargeGrid",
                    "used_strategy": "sim_init_stability",
                    "action_trace": ["stabilize start values"],
                },
                {
                    "failure_type": "model_check_error",
                    "model_id": "MediumPlant",
                    "used_strategy": "mc_connection_consistency",
                    "action_trace": ["fix connector mismatch"],
                },
            ]
        }
        payload = retrieve_repair_examples(
            history_payload=history,
            failure_type="simulate_error",
            model_hint="LargeGrid.mo",
            top_k=2,
        )
        self.assertEqual(int(payload.get("retrieved_count", 0)), 1)
        actions = payload.get("suggested_actions") if isinstance(payload.get("suggested_actions"), list) else []
        self.assertIn("stabilize start values", actions)

    def test_prefers_successful_rows_when_labels_exist(self) -> None:
        history = {
            "rows": [
                {
                    "failure_type": "simulate_error",
                    "model_id": "LargeGrid",
                    "used_strategy": "sim_init_stability_fail",
                    "action_trace": ["unsafe step size"],
                    "status": "FAIL",
                },
                {
                    "failure_type": "simulate_error",
                    "model_id": "LargeGrid",
                    "used_strategy": "sim_init_stability_pass",
                    "action_trace": ["stabilize start values"],
                    "status": "PASS",
                },
            ]
        }
        payload = retrieve_repair_examples(
            history_payload=history,
            failure_type="simulate_error",
            model_hint="LargeGrid.mo",
            top_k=2,
        )
        self.assertEqual(int(payload.get("retrieved_count", 0)), 1)
        examples = payload.get("examples") if isinstance(payload.get("examples"), list) else []
        self.assertEqual(str(examples[0].get("success_state") or ""), "success")
        actions = payload.get("suggested_actions") if isinstance(payload.get("suggested_actions"), list) else []
        self.assertEqual(actions, ["stabilize start values"])

    def test_supports_run_results_records_shape(self) -> None:
        history = {
            "records": [
                {
                    "task_id": "task_mdl_largegrid_simulate_error_1",
                    "failure_type": "simulate_error",
                    "passed": True,
                    "repair_strategy": {
                        "strategy_id": "sim_init_stability",
                        "actions": ["stabilize start values and initial equations near t=0"],
                    },
                    "repair_audit": {
                        "actions_planned": ["fallback action should be ignored if strategy actions exist"],
                    },
                }
            ]
        }
        payload = retrieve_repair_examples(
            history_payload=history,
            failure_type="simulate_error",
            model_hint="mdl_largegrid.mo",
            top_k=2,
        )
        self.assertEqual(int(payload.get("retrieved_count", 0)), 1)
        actions = payload.get("suggested_actions") if isinstance(payload.get("suggested_actions"), list) else []
        self.assertIn("stabilize start values and initial equations near t=0", actions)

    def test_policy_can_override_top_k_and_strategy_bonus(self) -> None:
        history = {
            "rows": [
                {
                    "failure_type": "simulate_error",
                    "model_id": "LargeGrid",
                    "used_strategy": "s1",
                    "action_trace": ["action-a"],
                    "status": "PASS",
                },
                {
                    "failure_type": "simulate_error",
                    "model_id": "LargeGrid",
                    "used_strategy": "s2",
                    "action_trace": ["action-b"],
                    "status": "PASS",
                },
            ]
        }
        payload = retrieve_repair_examples(
            history_payload=history,
            failure_type="simulate_error",
            model_hint="LargeGrid.mo",
            top_k=1,
            policy_payload={
                "top_k_by_failure_type": {"simulate_error": 2},
                "strategy_id_bonus_by_failure_type": {"simulate_error": {"s2": 1.0}},
                "failure_match_bonus": 2.0,
                "model_overlap_weight": 1.0,
            },
        )
        self.assertEqual(int(payload.get("effective_top_k", 0)), 2)
        self.assertEqual(int(payload.get("retrieved_count", 0)), 2)
        examples = payload.get("examples") if isinstance(payload.get("examples"), list) else []
        self.assertEqual(str(examples[0].get("strategy_id") or ""), "s2")

    def test_context_hints_prefer_matching_library_component_and_connector(self) -> None:
        history = {
            "rows": [
                {
                    "failure_type": "model_check_error",
                    "model_id": "HVACLoop",
                    "used_strategy": "mc_generic",
                    "action_trace": ["inspect declarations"],
                    "library_hints": ["buildings"],
                    "component_hints": ["mixingvolume"],
                    "connector_hints": ["port_a", "port_b"],
                    "status": "PASS",
                },
                {
                    "failure_type": "model_check_error",
                    "model_id": "HVACLoop",
                    "used_strategy": "mc_buildings_connector",
                    "action_trace": ["align fluid connector causality"],
                    "library_hints": ["buildings"],
                    "component_hints": ["mixingvolume", "boundary_p_t"],
                    "connector_hints": ["port_a", "heatport"],
                    "status": "PASS",
                },
            ]
        }
        payload = retrieve_repair_examples(
            history_payload=history,
            failure_type="model_check_error",
            model_hint="Buildings.Fluid.MixingVolumes.MixingVolume",
            top_k=1,
            context_hints={
                "library_hints": ["Buildings"],
                "component_hints": ["MixingVolume"],
                "connector_hints": ["HeatPort"],
                "text": ["connector mismatch on heatPort"],
            },
        )
        self.assertEqual(int(payload.get("retrieved_count", 0)), 1)
        examples = payload.get("examples") if isinstance(payload.get("examples"), list) else []
        self.assertEqual(str(examples[0].get("strategy_id") or ""), "mc_buildings_connector")
        self.assertIn("buildings", examples[0].get("matched_library_hints", []))
        self.assertIn("mixingvolume", examples[0].get("matched_component_hints", []))
        self.assertIn("heatport", examples[0].get("matched_connector_hints", []))

    def test_retrieval_audit_reports_domain_and_match_counts(self) -> None:
        history = {
            "rows": [
                {
                    "failure_type": "connector_mismatch",
                    "model_id": "OpenIPSL.Tests.Solar.PSAT.SolarPVTest",
                    "used_strategy": "curated_openipsl_connector_mismatch",
                    "action_trace": ["align bus electrical connector semantics"],
                    "library_hints": ["openipsl"],
                    "component_hints": ["solarpvtest", "spv"],
                    "connector_hints": ["gen1.p", "spv.p", "p"],
                    "domains": ["power_system"],
                    "status": "PASS",
                }
            ]
        }
        payload = retrieve_repair_examples(
            history_payload=history,
            failure_type="connector_mismatch",
            model_hint="OpenIPSL.Tests.Solar.PSAT.SolarPVTest",
            top_k=1,
            context_hints={
                "library_hints": ["openipsl"],
                "component_hints": ["SolarPVTest"],
                "connector_hints": ["p"],
                "domains": ["power_system"],
            },
        )
        audit = payload.get("audit") if isinstance(payload.get("audit"), dict) else {}
        self.assertEqual(int(audit.get("library_match_count", 0)), 1)
        self.assertEqual(int(audit.get("component_match_count", 0)), 1)
        self.assertGreaterEqual(int(audit.get("connector_match_count", 0)), 1)
        self.assertEqual(int(audit.get("domain_match_count", 0)), 1)
        self.assertIn("power_system", audit.get("matched_domain_hints", []))


if __name__ == "__main__":
    unittest.main()
