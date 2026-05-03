from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_v1_closeout_v0_58_0 import build_benchmark_v1_closeout, run_benchmark_v1_closeout


class BenchmarkV1CloseoutV058Tests(unittest.TestCase):
    def test_closeout_blocks_freeze_when_positive_solvability_is_missing(self) -> None:
        summary = build_benchmark_v1_closeout(
            spec_summary={"status": "PASS"},
            relayer_summary={},
            solvability_summary={"missing_positive_source_count": 2},
            medium_summary={"admitted_count": 3},
            split_summary={"readiness_status": "benchmark_split_provisional", "layer_counts": {"medium": 3, "hard": 5}},
            bundle_summary={"status": "PASS", "task_count": 8},
        )
        self.assertFalse(summary["freeze_ready"])
        self.assertIn("hard_positive_solvability_incomplete", summary["blockers"])
        self.assertFalse(summary["usable_now"]["full_solvable_benchmark_scoring"])

    def test_closeout_allows_freeze_when_all_blockers_clear(self) -> None:
        summary = build_benchmark_v1_closeout(
            spec_summary={"status": "PASS"},
            relayer_summary={},
            solvability_summary={"missing_positive_source_count": 0},
            medium_summary={"admitted_count": 3},
            split_summary={"readiness_status": "benchmark_split_ready", "layer_counts": {"medium": 3, "hard": 5}},
            bundle_summary={"status": "PASS", "task_count": 8},
        )
        self.assertTrue(summary["freeze_ready"])
        self.assertEqual(summary["status"], "PASS")

    def test_run_closeout_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {}
            payloads = {
                "spec": '{"status":"PASS"}',
                "relayer": "{}",
                "solvability": '{"missing_positive_source_count":0}',
                "medium": '{"admitted_count":1}',
                "split": '{"readiness_status":"benchmark_split_ready","layer_counts":{"medium":1,"hard":1}}',
                "bundle": '{"status":"PASS","task_count":2}',
            }
            for name, payload in payloads.items():
                files[name] = root / f"{name}.json"
                files[name].write_text(payload, encoding="utf-8")
            out = root / "out"
            summary = run_benchmark_v1_closeout(
                spec_path=files["spec"],
                relayer_path=files["relayer"],
                solvability_path=files["solvability"],
                medium_path=files["medium"],
                split_path=files["split"],
                bundle_path=files["bundle"],
                out_dir=out,
            )
            self.assertTrue(summary["freeze_ready"])
            self.assertTrue((out / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
