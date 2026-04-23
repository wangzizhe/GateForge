import tempfile
import time
import unittest
from pathlib import Path

from gateforge.agent_modelica_trajectory_store_v1 import (
    SCHEMA_VERSION,
    abstract_root_cause_signature,
    build_trajectory_store,
    extract_trajectory_entries_from_result,
    load_trajectory_store,
    query_to_search_text,
    retrieve_similar_trajectories,
    vectorize_text,
)


class AgentModelicaTrajectoryStoreV1Tests(unittest.TestCase):
    def test_extracts_round_entries_without_variable_names_in_search_key(self) -> None:
        payload = {
            "candidate_id": "v01945_SyncMachineSimplified_v0_pp_tpd0__pv_PSIppd_phantom",
            "mode": "baseline-c5",
            "final_status": "pass",
            "round_count": 2,
            "rounds": [
                {
                    "round": 1,
                    "omc_output": "Warning: The following variables are not fully defined: PSIppd_phantom, EFD.",
                    "advance": "continue",
                    "ranked": [
                        {"check_pass": False, "simulate_pass": False, "deficit": 3},
                        {"check_pass": True, "simulate_pass": False, "deficit": 1},
                    ],
                }
            ],
        }

        entries = extract_trajectory_entries_from_result(payload, source_path="fake.json")

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["mutation_family"], "compound_underdetermined")
        search_text = entries[0]["search_text"]
        signature_text = str(entries[0]["abstract_signature"])
        self.assertIn("compound_underdetermined", search_text)
        self.assertNotIn("PSIppd", search_text)
        self.assertNotIn("EFD", search_text)
        self.assertNotIn("PSIppd", signature_text)
        self.assertNotIn("EFD", signature_text)

    def test_retrieval_prefers_same_abstract_family_and_failure(self) -> None:
        pass_payload = {
            "candidate_id": "case_pp_a_pv_b",
            "mode": "multi-c5",
            "final_status": "pass",
            "round_count": 2,
            "rounds": [
                {
                    "round": 1,
                    "omc_output": "The model has 9 equation(s) and 12 variable(s). It is underdetermined.",
                    "advance": "continue",
                    "ranked": [{"check_pass": True, "simulate_pass": True, "deficit": 3}],
                }
            ],
        }
        fail_payload = {
            "candidate_id": "case_overdet",
            "mode": "baseline",
            "final_status": "fail",
            "round_count": 1,
            "rounds": [
                {
                    "round": 1,
                    "omc_output": "The model is overdetermined: too many equations.",
                    "advance": "fail",
                    "ranked": [{"check_pass": False, "simulate_pass": False, "deficit": 0}],
                }
            ],
        }
        store = {
            "schema_version": "gateforge_trajectory_store_v1",
            "vector_dim": 512,
            "entries": extract_trajectory_entries_from_result(pass_payload, source_path="pass.json")
            + extract_trajectory_entries_from_result(fail_payload, source_path="fail.json"),
        }

        result = retrieve_similar_trajectories(
            store,
            {
                "mutation_family": "compound_underdetermined",
                "failure_type": "underdetermined_structural",
                "abstract_signature": {
                    "mutation_family": "compound_underdetermined",
                    "failure_type": "underdetermined_structural",
                    "has_parameter_promotion_marker": True,
                    "has_phantom_marker": True,
                },
            },
            top_k=1,
        )

        hits = result["hits"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["mutation_family"], "compound_underdetermined")

    def test_build_store_from_directory_counts_success_and_failure(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "pass.json").write_text(
                """
{
  "candidate_id": "case_pp_x_pv_y",
  "mode": "multi-c5",
  "final_status": "pass",
  "rounds": [{"round": 1, "omc_output": "underdetermined", "ranked": []}]
}
""",
                encoding="utf-8",
            )
            (root / "fail.json").write_text(
                """
{
  "candidate_id": "case_pv_y",
  "mode": "baseline",
  "final_status": "fail",
  "rounds": [{"round": 1, "omc_output": "underdetermined", "ranked": []}]
}
""",
                encoding="utf-8",
            )
            (root / "summary.json").write_text("{}", encoding="utf-8")

            store = build_trajectory_store([root])

        self.assertEqual(store["entry_count"], 2)
        self.assertEqual(store["success_count"], 1)
        self.assertEqual(store["failure_count"], 1)

    def test_retrieval_latency_under_budget_on_synthetic_store(self) -> None:
        entries = []
        for index in range(250):
            payload = {
                "candidate_id": f"case_pp_{index}_pv_{index}",
                "mode": "multi-c5",
                "final_status": "pass" if index % 2 == 0 else "fail",
                "rounds": [
                    {
                        "round": 1,
                        "omc_output": "The model is underdetermined with too few equations.",
                        "ranked": [{"check_pass": index % 3 == 0, "simulate_pass": index % 5 == 0, "deficit": 3}],
                    }
                ],
            }
            entries.extend(extract_trajectory_entries_from_result(payload, source_path=f"{index}.json"))
        store = {"schema_version": "gateforge_trajectory_store_v1", "vector_dim": 512, "entries": entries}

        started = time.perf_counter()
        result = retrieve_similar_trajectories(
            store,
            {"mutation_family": "compound_underdetermined", "failure_type": "underdetermined_structural"},
            top_k=5,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        self.assertLess(elapsed_ms, 500.0)
        self.assertLess(result["latency_ms"], 500.0)
        self.assertEqual(len(result["hits"]), 5)

    def test_signature_uses_counts_not_raw_symbols(self) -> None:
        signature = abstract_root_cause_signature(
            {
                "candidate_id": "v01945_ThermalZone_v0_pp_c1_c2_pv_phi1",
                "rounds": [],
            },
            {"omc_output": "Variable Tw is not determined. Variable phi1_phantom is not determined."},
        )

        self.assertEqual(signature["mutation_family"], "compound_underdetermined")
        self.assertEqual(signature["phantom_token_count"], 1)
        self.assertNotIn("Tw", str(signature))
        self.assertNotIn("phi1", str(signature))

    def test_query_to_search_text_handles_empty_and_none_signature(self) -> None:
        with_none = query_to_search_text(
            {
                "mutation_family": "compound_underdetermined",
                "failure_type": "underdetermined_structural",
                "mode": "baseline-c5",
                "abstract_signature": None,
            }
        )
        empty_query = query_to_search_text({})

        self.assertEqual(
            with_none,
            "family:compound_underdetermined failure:underdetermined_structural mode:baseline_c5",
        )
        self.assertEqual(empty_query, "family:unknown failure:unknown mode:unknown")
        self.assertNotIn("mutation_family:", with_none)
        self.assertNotIn("failure_type:", with_none)

    def test_load_trajectory_store_rejects_schema_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "store.json"
            path.write_text('{"schema_version":"wrong_schema","entries":[]}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_trajectory_store(path)

    def test_abstract_token_mapping_boundaries(self) -> None:
        phantom_vec = vectorize_text("node_phantom")
        exact_vec = vectorize_text("phantom")
        unrelated_vec = vectorize_text("phantom_size")
        number_vec = vectorize_text("12.5")

        self.assertEqual(phantom_vec, exact_vec)
        self.assertNotEqual(phantom_vec, unrelated_vec)
        self.assertNotEqual(number_vec, {})


if __name__ == "__main__":
    unittest.main()
