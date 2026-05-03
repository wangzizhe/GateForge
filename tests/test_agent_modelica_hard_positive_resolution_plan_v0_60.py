from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_hard_positive_resolution_plan_v0_60_2 import (
    build_hard_positive_resolution_plan,
    classify_resolution_bucket,
    run_hard_positive_resolution_plan,
)


class HardPositiveResolutionPlanV060Tests(unittest.TestCase):
    def test_classify_resolution_bucket_identifies_near_miss(self) -> None:
        self.assertEqual(classify_resolution_bucket({"case_id": "sem_29_two_branch_probe_bus"}), "near_miss_reference_queue")
        self.assertEqual(
            classify_resolution_bucket({"case_id": "sem_32_four_segment_adapter_cross_node", "reference_strategy": "adapter_contract_reference_repair_required"}),
            "adapter_contract_frontier_unresolved",
        )

    def test_resolution_plan_excludes_frontier_from_solvable_scoring(self) -> None:
        summary = build_hard_positive_resolution_plan(
            workbench_summary={
                "results": [
                    {"case_id": "sem_29_two_branch_probe_bus", "reference_strategy": "probe_flow_ownership_reference_repair_required"},
                    {"case_id": "sem_32_four_segment_adapter_cross_node", "reference_strategy": "adapter_contract_reference_repair_required"},
                ]
            },
            attempts_summary={"failed_attempt_count": 2},
        )
        self.assertEqual(summary["near_miss_reference_queue_case_ids"], ["sem_29_two_branch_probe_bus"])
        self.assertEqual(summary["frontier_unresolved_case_ids"], ["sem_32_four_segment_adapter_cross_node"])
        self.assertFalse(summary["benchmark_policy"]["frontier_unresolved_counts_in_solvable_scoring"])

    def test_run_resolution_plan_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workbench = root / "workbench.json"
            attempts = root / "attempts.json"
            workbench.write_text('{"results":[{"case_id":"sem_32_four_segment_adapter_cross_node","reference_strategy":"adapter_contract_reference_repair_required"}]}', encoding="utf-8")
            attempts.write_text('{"failed_attempt_count":1}', encoding="utf-8")
            out = root / "out"
            summary = run_hard_positive_resolution_plan(workbench_path=workbench, attempts_path=attempts, out_dir=out)
            self.assertEqual(summary["frontier_unresolved_count"], 1)
            self.assertTrue((out / "frontier_unresolved_case_ids.txt").exists())


if __name__ == "__main__":
    unittest.main()
