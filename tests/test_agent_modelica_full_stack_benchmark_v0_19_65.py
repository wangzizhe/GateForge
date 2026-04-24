from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_full_stack_benchmark_v0_19_65 import (
    build_capability_gate_summary,
    run_full_stack_benchmark,
    summarize_arm,
)


class FullStackBenchmarkV01965Tests(unittest.TestCase):
    def test_summarize_arm_computes_clean_pass_and_coverage(self) -> None:
        rows = [
            {
                "candidate_id": "a",
                "final_status": "pass",
                "round_count": 1,
                "num_candidates_per_round": 5,
                "rounds": [
                    {
                        "num_candidates": 5,
                        "any_simulate_pass": True,
                        "coverage_simulate_pass": 2,
                    }
                ],
            },
            {
                "candidate_id": "b",
                "final_status": "fail",
                "round_count": 1,
                "num_candidates_per_round": 5,
                "rounds": [
                    {
                        "num_candidates": 5,
                        "any_simulate_pass": False,
                        "coverage_simulate_pass": 0,
                    }
                ],
            },
        ]

        summary = summarize_arm(rows, arm_name="stack")

        self.assertEqual(summary["pass_count"], 1)
        self.assertEqual(summary["clean_pass_rate"], 0.5)
        self.assertEqual(summary["per_round_any_simulate_pass_rate"], 0.5)
        self.assertEqual(summary["pooled_simulate_pass_rate"], 0.2)

    def test_capability_gate_summary_keeps_negative_capabilities_disabled(self) -> None:
        gates = build_capability_gate_summary(
            retrieval_attribution={"mechanism_counts": {"retrieval_diluted_current_omc_signal": 3}},
            candidate_distill={"admitted_count": 12, "isolation_status": "isolated_pool_not_main_benchmark"},
            model_comparison={"status": "PARTIAL", "blocked_profiles": [{"model": "claude"}]},
        )

        disabled = {row["capability"]: row["decision"] for row in gates["disabled_or_caveated_capabilities"]}
        self.assertEqual(disabled["retrieval_augmented_repair_default"], "disabled")
        self.assertEqual(disabled["multi_model_generalization_claim"], "caveat")
        self.assertEqual(gates["isolated_candidate_pool"]["admitted_count"], 12)

    def test_run_full_stack_benchmark_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mc_dir = root / "multi"
            mc_dir.mkdir()
            for mode, statuses in {
                "baseline": ["pass", "fail", "fail", "fail"],
                "multi-c5": ["pass", "pass", "fail", "fail"],
            }.items():
                for idx, status in enumerate(statuses):
                    payload = {
                        "candidate_id": f"case_{idx}",
                        "mode": mode,
                        "final_status": status,
                        "round_count": 1,
                        "num_candidates_per_round": 5 if mode == "multi-c5" else 1,
                        "rounds": [
                            {
                                "num_candidates": 5 if mode == "multi-c5" else 1,
                                "any_simulate_pass": status == "pass",
                                "coverage_simulate_pass": 1 if status == "pass" else 0,
                            }
                        ],
                    }
                    (mc_dir / f"case_{idx}_{mode}.json").write_text(json.dumps(payload), encoding="utf-8")
            retrieval = root / "retrieval.json"
            candidates = root / "candidates.json"
            model = root / "model.json"
            retrieval.write_text(json.dumps({"transition_counts": {"retrieval_regression": 1}}), encoding="utf-8")
            candidates.write_text(json.dumps({"admitted_count": 3, "isolation_status": "isolated"}), encoding="utf-8")
            model.write_text(json.dumps({"status": "PARTIAL"}), encoding="utf-8")

            summary = run_full_stack_benchmark(
                multi_candidate_dir=mc_dir,
                retrieval_attribution_path=retrieval,
                candidate_distill_path=candidates,
                model_comparison_path=model,
                out_dir=root / "out",
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["baseline_arm"]["pass_count"], 1)
            self.assertEqual(summary["full_stack_arm"]["pass_count"], 2)
            self.assertTrue((root / "out" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()

