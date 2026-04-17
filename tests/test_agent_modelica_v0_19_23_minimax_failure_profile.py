from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_minimax_failure_profile_v0_19_23 import (  # noqa: E402
    build_failure_profile,
    classify_error_message,
)


class V01923MiniMaxFailureProfileTests(unittest.TestCase):
    def test_classify_error_message_provider_timeout(self) -> None:
        self.assertEqual(
            classify_error_message("minimax_request_timeout"),
            "provider_timeout",
        )

    def test_classify_error_message_provider_overloaded(self) -> None:
        self.assertEqual(
            classify_error_message("minimax_http_error:529:{\"type\":\"error\",\"error\":{\"type\":\"overloaded_error\"}}"),
            "provider_overloaded_529",
        )

    def test_build_failure_profile_counts_infra_failures(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            summary_path = root / "summary.json"
            raw_dir = root / "raw"
            raw_dir.mkdir()

            summary = {
                "aggregate": {"pass_rate": 0.684},
                "summaries": [
                    {
                        "candidate_id": "case_timeout",
                        "benchmark_family": "underdetermined_missing_ground",
                        "executor_status": "FAILED",
                        "n_turns": 2,
                        "observed_error_sequence": ["simulate_error", "simulate_error"],
                    },
                    {
                        "candidate_id": "case_529",
                        "benchmark_family": "compound_four_layer",
                        "executor_status": "FAILED",
                        "n_turns": 1,
                        "observed_error_sequence": ["simulate_error"],
                    },
                    {
                        "candidate_id": "case_pass",
                        "benchmark_family": "semantic_time_constant",
                        "executor_status": "PASS",
                        "n_turns": 2,
                        "observed_error_sequence": ["behavioral_contract_fail", "none"],
                    },
                ],
            }
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            (raw_dir / "case_timeout.json").write_text(
                json.dumps({"error_message": "minimax_request_timeout"}),
                encoding="utf-8",
            )
            (raw_dir / "case_529.json").write_text(
                json.dumps({"error_message": "minimax_http_error:529:{\"type\":\"error\",\"error\":{\"type\":\"overloaded_error\"}}"}),
                encoding="utf-8",
            )

            report = build_failure_profile(summary_path, raw_dir)

        self.assertEqual(report["failed_case_count"], 2)
        self.assertEqual(report["failure_class_counts"]["provider_timeout"], 1)
        self.assertEqual(report["failure_class_counts"]["provider_overloaded_529"], 1)
        self.assertEqual(report["infra_failure_total"], 2)
        self.assertEqual(report["capability_failure_total"], 0)
        self.assertEqual(
            report["targeted_family_failure_profile"]["underdetermined_missing_ground"]["failure_classes"]["provider_timeout"],
            1,
        )
        self.assertEqual(
            report["targeted_family_failure_profile"]["compound_four_layer"]["failure_classes"]["provider_overloaded_529"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
