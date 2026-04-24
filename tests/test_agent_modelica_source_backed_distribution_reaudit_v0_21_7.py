from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_source_backed_distribution_reaudit_v0_21_7 import (
    admitted_counts,
    build_source_backed_distribution_reaudit,
    run_source_backed_distribution_reaudit,
)


def _generation_summary() -> dict:
    return {"generation_failure_distribution_p": {"ET01": 0.5, "ET02": 0.25, "ET07": 0.25}}


def _taxonomy_summary() -> dict:
    return {"bucket_counts": {"ET07": 2, "ET08": 2}}


def _admitted(bucket_id: str) -> dict:
    return {"bucket_id": bucket_id, "benchmark_admission_status": "main_admissible_source_target_pair"}


class SourceBackedDistributionReauditV0217Tests(unittest.TestCase):
    def test_admitted_counts_uses_only_main_admissible_pairs(self) -> None:
        counts = admitted_counts(
            [
                _admitted("ET01"),
                {"bucket_id": "ET02", "benchmark_admission_status": "blocked_from_main_benchmark"},
            ]
        )

        self.assertEqual(counts, {"ET01": 1})

    def test_build_source_backed_distribution_reaudit_reports_improvement(self) -> None:
        summary = build_source_backed_distribution_reaudit(
            generation_summary=_generation_summary(),
            taxonomy_summary=_taxonomy_summary(),
            target_admission_rows=[_admitted("ET01"), _admitted("ET02")],
        )

        self.assertEqual(summary["status"], "PASS")
        self.assertLess(summary["updated_distance"], summary["previous_distance"])

    def test_run_source_backed_distribution_reaudit_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generation_path = root / "generation.json"
            taxonomy_path = root / "taxonomy.json"
            admission_path = root / "admission.jsonl"
            out_dir = root / "out"
            generation_path.write_text(json.dumps(_generation_summary()), encoding="utf-8")
            taxonomy_path.write_text(json.dumps(_taxonomy_summary()), encoding="utf-8")
            admission_path.write_text(
                "\n".join([json.dumps(_admitted("ET01")), json.dumps(_admitted("ET02"))]),
                encoding="utf-8",
            )

            summary = run_source_backed_distribution_reaudit(
                generation_summary_path=generation_path,
                taxonomy_summary_path=taxonomy_path,
                target_admission_path=admission_path,
                out_dir=out_dir,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())


if __name__ == "__main__":
    unittest.main()
