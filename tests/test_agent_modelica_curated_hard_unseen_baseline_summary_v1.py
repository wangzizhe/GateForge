import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AgentModelicaCuratedHardUnseenBaselineSummaryV1Tests(unittest.TestCase):
    def test_baseline_summary_aggregates_seen_risk_and_source_type(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            challenge = root / "challenge.json"
            baseline_summary = root / "baseline_summary.json"
            baseline_results = root / "baseline_results.json"
            _write_json(
                taskset,
                {
                    "tasks": [
                        {
                            "task_id": "t1",
                            "seen_risk_band": "hard_unseen",
                            "source_type": "internal_mirror",
                            "source_meta": {"library_id": "liba", "model_id": "ma", "qualified_model_name": "LibA.A"},
                        },
                        {
                            "task_id": "t2",
                            "seen_risk_band": "less_likely_seen",
                            "source_type": "public_repo",
                            "source_meta": {"library_id": "libb", "model_id": "mb", "qualified_model_name": "LibB.B"},
                        },
                    ]
                },
            )
            _write_json(
                challenge,
                {
                    "taskset_frozen_path": str(taskset),
                    "total_tasks": 2,
                    "counts_by_library": {"liba": 1, "libb": 1},
                    "counts_by_seen_risk_band": {"hard_unseen": 1, "less_likely_seen": 1},
                    "counts_by_source_type": {"internal_mirror": 1, "public_repo": 1},
                },
            )
            _write_json(baseline_summary, {"status": "PASS", "success_count": 1, "success_at_k_pct": 50.0})
            _write_json(
                baseline_results,
                {
                    "records": [
                        {"task_id": "t1", "passed": True},
                        {
                            "task_id": "t2",
                            "passed": False,
                            "error_message": "no_progress_stop",
                            "attempts": [
                                {
                                    "round": 1,
                                    "observed_failure_type": "model_check_error",
                                    "reason": "connector mismatch",
                                    "source_repair": {"applied": True, "reason": "restored_source_model_text_for_connector_mismatch"},
                                },
                                {"round": 2, "observed_failure_type": "simulate_error", "reason": "initialization failed"},
                            ],
                        },
                    ]
                },
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_curated_hard_unseen_baseline_summary_v1",
                    "--challenge-summary",
                    str(challenge),
                    "--baseline-summary",
                    str(baseline_summary),
                    "--baseline-results",
                    str(baseline_results),
                    "--out",
                    str(root / "out.json"),
                    "--source-unstable-exclusions-out",
                    str(root / "exclusions.json"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            out = json.loads((root / "out.json").read_text(encoding="utf-8"))
            exclusions = json.loads((root / "exclusions.json").read_text(encoding="utf-8"))
            self.assertEqual(out.get("success_by_seen_risk_band", {}).get("hard_unseen", {}).get("success_at_k_pct"), 100.0)
            self.assertEqual(out.get("success_by_seen_risk_band", {}).get("less_likely_seen", {}).get("success_at_k_pct"), 0.0)
            self.assertEqual(out.get("success_by_source_type", {}).get("internal_mirror", {}).get("success_at_k_pct"), 100.0)
            self.assertEqual(out.get("source_unstable_summary", {}).get("model_count"), 1)
            self.assertEqual(exclusions.get("qualified_model_names"), ["LibB.B"])


if __name__ == "__main__":
    unittest.main()
