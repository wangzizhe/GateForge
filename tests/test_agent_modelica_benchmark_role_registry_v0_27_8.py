from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_role_registry_v0_27_8 import (
    ROLE_CAPABILITY_BASELINE,
    ROLE_DIAGNOSTIC,
    ROLE_HARD_NEGATIVE,
    build_benchmark_role_registry,
    run_benchmark_role_registry,
)


class BenchmarkRoleRegistryV0278Tests(unittest.TestCase):
    def test_build_registry_separates_roles(self) -> None:
        manifest_rows = [
            {"candidate_id": "h1", "mutation_family": "hard_family", "split": "hard_negative", "repeatability_class": "stable_dead_end"},
            {"candidate_id": "b1", "mutation_family": "baseline_family", "split": "positive", "repeatability_class": "stable_true_multi"},
            {"candidate_id": "d1", "mutation_family": "diagnostic_family", "split": "positive", "repeatability_class": "mixed_non_success"},
        ]
        repeatability_summary = {
            "candidate_summaries": [
                {"candidate_id": "b1", "mutation_family": "baseline_family", "stability": "stable_true_multi"},
                {"candidate_id": "b2", "mutation_family": "baseline_family", "stability": "stable_true_multi"},
                {"candidate_id": "d1", "mutation_family": "diagnostic_family", "stability": "stable_true_multi"},
                {"candidate_id": "d2", "mutation_family": "diagnostic_family", "stability": "never_true_multi"},
            ]
        }
        hard_negative_summary = {"family": "hard_family", "decision": "treat_family_as_current_hard_negative"}
        registry, summary = build_benchmark_role_registry(
            manifest_rows=manifest_rows,
            repeatability_summary=repeatability_summary,
            hard_negative_summary=hard_negative_summary,
        )
        by_family = {row["family"]: row for row in registry}
        self.assertEqual(by_family["hard_family"]["role"], ROLE_HARD_NEGATIVE)
        self.assertEqual(by_family["baseline_family"]["role"], ROLE_CAPABILITY_BASELINE)
        self.assertEqual(by_family["diagnostic_family"]["role"], ROLE_DIAGNOSTIC)
        self.assertEqual(summary["decision"], "benchmark_roles_ready_for_slice_selection")
        self.assertFalse(summary["discipline"]["deterministic_repair_added"])

    def test_run_registry_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.jsonl"
            repeatability = root / "repeatability.json"
            hard_negative = root / "hard.json"
            manifest.write_text(
                json.dumps({"candidate_id": "c1", "mutation_family": "family", "split": "positive", "repeatability_class": "stable_true_multi"}) + "\n",
                encoding="utf-8",
            )
            repeatability.write_text(
                json.dumps(
                    {
                        "candidate_summaries": [
                            {"candidate_id": "c1", "mutation_family": "family", "stability": "stable_true_multi"},
                            {"candidate_id": "c2", "mutation_family": "family", "stability": "stable_true_multi"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            hard_negative.write_text(json.dumps({}), encoding="utf-8")
            summary = run_benchmark_role_registry(
                manifest_path=manifest,
                repeatability_summary_path=repeatability,
                hard_negative_summary_path=hard_negative,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "family_roles.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
