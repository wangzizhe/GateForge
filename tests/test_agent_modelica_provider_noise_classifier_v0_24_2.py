from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_provider_noise_classifier_v0_24_2 import (
    build_provider_noise_report,
    classify_noise,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class ProviderNoiseClassifierV0242Tests(unittest.TestCase):
    def test_classify_noise_separates_provider_infra_and_llm_failure(self) -> None:
        self.assertEqual(classify_noise({"provider_failure": True}), "provider_failure")
        self.assertEqual(classify_noise({"final_verdict": "503 service unavailable"}), "provider_503")
        self.assertEqual(classify_noise({"feedback_sequence": ["Class Modelica not found in scope"]}), "infra_msl_load_error")
        self.assertEqual(classify_noise({"trajectory_class": "multi_turn_useful"}), "llm_success")
        self.assertEqual(classify_noise({"trajectory_class": "multi_turn_failed_or_dead_end"}), "llm_or_task_failure")

    def test_build_provider_noise_report_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trajectory_path = root / "trajectories.jsonl"
            out_dir = root / "out"
            _write_jsonl(
                trajectory_path,
                [
                    {"case_id": "a", "trajectory_class": "multi_turn_useful", "final_verdict": "PASS"},
                    {"case_id": "b", "trajectory_class": "multi_turn_failed_or_dead_end", "final_verdict": "FAILED"},
                    {"case_id": "c", "final_verdict": "timeout"},
                ],
            )

            summary = build_provider_noise_report(trajectory_paths=[trajectory_path], out_dir=out_dir)

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["provider_noise_count"], 1)
            self.assertEqual(summary["llm_success_count"], 1)
            self.assertEqual(summary["llm_failure_count"], 1)
            self.assertTrue((out_dir / "noise_rows.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
