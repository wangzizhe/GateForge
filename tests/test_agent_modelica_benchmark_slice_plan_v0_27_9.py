from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_slice_plan_v0_27_9 import (
    build_benchmark_slice_plan,
    run_benchmark_slice_plan,
)


class BenchmarkSlicePlanV0279Tests(unittest.TestCase):
    def test_build_plan_keeps_roles_separate(self) -> None:
        role_rows = [
            {"family": "base", "role": "capability_baseline_candidate"},
            {"family": "hard", "role": "hard_negative"},
            {"family": "diag", "role": "diagnostic"},
        ]
        manifest_rows = [
            {"candidate_id": "b1", "mutation_family": "base", "split": "positive", "repeatability_class": "stable_true_multi"},
            {"candidate_id": "b2", "mutation_family": "base", "split": "research_pool", "repeatability_class": "unstable_true_multi"},
            {"candidate_id": "h1", "mutation_family": "hard", "split": "hard_negative", "repeatability_class": "stable_dead_end"},
            {"candidate_id": "d1", "mutation_family": "diag", "split": "positive", "repeatability_class": "stable_true_multi"},
        ]
        planned, summary = build_benchmark_slice_plan(
            role_rows=role_rows,
            manifest_rows=manifest_rows,
            max_per_slice=2,
        )
        by_id = {row["candidate_id"]: row for row in planned}
        self.assertEqual(by_id["b1"]["slice_role"], "capability_baseline")
        self.assertNotIn("b2", by_id)
        self.assertEqual(by_id["h1"]["slice_role"], "hard_negative")
        self.assertEqual(by_id["d1"]["slice_role"], "diagnostic")
        self.assertFalse(summary["mixed_pass_rate_allowed"])

    def test_run_plan_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roles = root / "roles.jsonl"
            manifest = root / "manifest.jsonl"
            roles.write_text(json.dumps({"family": "base", "role": "capability_baseline_candidate"}) + "\n", encoding="utf-8")
            manifest.write_text(
                json.dumps({"candidate_id": "b1", "mutation_family": "base", "split": "positive", "repeatability_class": "stable_true_multi"}) + "\n",
                encoding="utf-8",
            )
            summary = run_benchmark_slice_plan(
                role_registry_path=roles,
                manifest_path=manifest,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "slice_plan.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
