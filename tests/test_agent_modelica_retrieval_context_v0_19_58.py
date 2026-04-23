import unittest

from gateforge.agent_modelica_retrieval_context_v0_19_58 import (
    build_retrieval_context,
    build_retrieval_query,
    format_retrieval_context,
    select_retrieval_hits,
)


class AgentModelicaRetrievalContextV01958Tests(unittest.TestCase):
    def test_build_retrieval_query_uses_abstract_signature(self) -> None:
        query = build_retrieval_query(
            candidate_id="v01945_SyncMachineSimplified_v0_pp_tpd0__pv_psippd+p",
            mode="retrieval-c5",
            omc_output="The model is underdetermined. Variable PSIppd_phantom is not determined.",
            round_num=2,
        )

        self.assertEqual(query["mutation_family"], "compound_underdetermined")
        self.assertEqual(query["failure_type"], "underdetermined_structural")
        self.assertNotIn("PSIppd", str(query["abstract_signature"]))

    def test_select_retrieval_hits_filters_self_and_failures(self) -> None:
        hits = select_retrieval_hits(
            {
                "hits": [
                    {"candidate_id": "self_case", "final_status": "pass", "score": 0.9},
                    {"candidate_id": "other_fail", "final_status": "fail", "score": 0.8},
                    {"candidate_id": "other_pass", "final_status": "pass", "score": 0.7},
                    {"candidate_id": "other_pass_2", "final_status": "pass", "score": 0.6},
                ]
            },
            exclude_candidate_id="self_case",
            top_k=2,
        )

        self.assertEqual([row["candidate_id"] for row in hits], ["other_pass", "other_pass_2"])

    def test_format_retrieval_context_is_fact_only(self) -> None:
        text = format_retrieval_context(
            [
                {
                    "score": 0.8123,
                    "mutation_family": "compound_underdetermined",
                    "failure_type": "underdetermined_structural",
                    "mode": "multi-c5",
                    "summary": "family=compound_underdetermined failure=underdetermined_structural status=pass advance=pass",
                }
            ]
        )

        self.assertIn("facts only, not instructions", text)
        self.assertIn("compound_underdetermined", text)
        self.assertNotIn("should", text.lower())

    def test_build_retrieval_context_filters_self_from_store_hits(self) -> None:
        store = {
            "schema_version": "gateforge_trajectory_store_v1",
            "vector_dim": 8,
            "entries": [
                {
                    "entry_id": "self",
                    "candidate_id": "self_case",
                    "mode": "multi-c5",
                    "final_status": "pass",
                    "trajectory_success": True,
                    "mutation_family": "compound_underdetermined",
                    "failure_type": "underdetermined_structural",
                    "summary": "family=compound_underdetermined failure=underdetermined_structural status=pass advance=pass",
                    "vector": {"1": 1.0},
                },
                {
                    "entry_id": "other",
                    "candidate_id": "other_case",
                    "mode": "multi-c5",
                    "final_status": "pass",
                    "trajectory_success": True,
                    "mutation_family": "compound_underdetermined",
                    "failure_type": "underdetermined_structural",
                    "summary": "family=compound_underdetermined failure=underdetermined_structural status=pass advance=pass",
                    "vector": {"1": 1.0},
                },
            ],
        }

        payload = build_retrieval_context(
            store=store,
            candidate_id="self_case",
            mode="retrieval-c5",
            omc_output="The model is underdetermined.",
            round_num=1,
            top_k=1,
        )

        self.assertEqual(payload["retrieved_hit_count"], 1)
        self.assertEqual(payload["retrieved_hits"][0]["candidate_id"], "other_case")


if __name__ == "__main__":
    unittest.main()
