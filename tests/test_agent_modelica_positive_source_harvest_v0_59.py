from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_positive_source_harvest_v0_59_0 import (
    build_positive_source_harvest,
    discover_reference_repair_paths,
    harvest_successful_trajectories,
    run_positive_source_harvest,
)


class PositiveSourceHarvestV059Tests(unittest.TestCase):
    def test_harvest_successful_trajectories_requires_pass_and_submit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            path.write_text(
                '{"case_id":"case_a","final_verdict":"PASS","submitted":true,"provider_error":"","final_model_text":"model A end A;"}\n'
                '{"case_id":"case_b","final_verdict":"PASS","submitted":false,"provider_error":"","final_model_text":"model B end B;"}\n',
                encoding="utf-8",
            )
            rows = harvest_successful_trajectories(hard_case_ids=["case_a", "case_b"], result_paths=[path])
        self.assertIn("case_a", rows)
        self.assertNotIn("case_b", rows)

    def test_reference_paths_are_grouped_by_case_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "v1").mkdir()
            (root / "v1" / "case_a.json").write_text("{}", encoding="utf-8")
            grouped = discover_reference_repair_paths(root)
        self.assertIn("case_a", grouped)

    def test_build_harvest_reports_missing_cases_without_leaking_prompt_sources(self) -> None:
        summary, records = build_positive_source_harvest(
            hard_pack_summary={"hard_case_ids": ["case_a", "case_b"]},
            result_paths=[],
            reference_paths_by_case={"case_a": ["private/ref/case_a.json"]},
        )
        self.assertEqual(summary["positive_source_case_ids"], ["case_a"])
        self.assertEqual(summary["missing_positive_source_case_ids"], ["case_b"])
        self.assertFalse(summary["prompt_visibility_contract"]["positive_sources_enter_agent_prompt"])
        self.assertFalse(records[0]["prompt_visible"])

    def test_run_harvest_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hard = root / "hard.json"
            hard.write_text('{"hard_case_ids":["case_a"]}', encoding="utf-8")
            artifact_root = root / "artifacts"
            run_dir = artifact_root / "run"
            run_dir.mkdir(parents=True)
            (run_dir / "results.jsonl").write_text(
                '{"case_id":"case_a","final_verdict":"PASS","submitted":true,"provider_error":"","final_model_text":"model A end A;"}\n',
                encoding="utf-8",
            )
            out = root / "out"
            summary = run_positive_source_harvest(hard_pack_path=hard, artifact_root=artifact_root, reference_root=root / "refs", out_dir=out)
            self.assertEqual(summary["positive_source_case_count"], 1)
            self.assertTrue((out / "positive_sources.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
