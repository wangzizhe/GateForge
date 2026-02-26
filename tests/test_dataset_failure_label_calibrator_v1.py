import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureLabelCalibratorV1Tests(unittest.TestCase):
    def test_calibrator_builds_replay_observations(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            raw = root / "raw.json"
            replay = root / "replay.json"
            out = root / "summary.json"

            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutation_id": "m1", "expected_failure_type": "simulate_error"},
                            {"mutation_id": "m2", "expected_failure_type": "model_check_error"},
                            {"mutation_id": "m3", "expected_failure_type": "semantic_regression"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            raw.write_text(
                json.dumps(
                    {
                        "schema_version": "mutation_raw_observations_v1",
                        "observations": [
                            {
                                "mutation_id": "m1",
                                "target_model_id": "mdl_a",
                                "target_scale": "medium",
                                "attempts": [{"return_code": 2, "timed_out": False, "stderr": "solver failed in simulation"}],
                            },
                            {
                                "mutation_id": "m2",
                                "target_model_id": "mdl_b",
                                "target_scale": "large",
                                "attempts": [{"return_code": 1, "timed_out": False, "stderr": "model check type mismatch"}],
                            },
                            {
                                "mutation_id": "m3",
                                "target_model_id": "mdl_c",
                                "target_scale": "small",
                                "attempts": [{"return_code": 0, "timed_out": False, "stdout": "ok", "stderr": ""}],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_label_calibrator_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--raw-observations",
                    str(raw),
                    "--replay-observations-out",
                    str(replay),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("total_observations", 0)), 3)
            self.assertGreaterEqual(int(summary.get("auto_override_count", 0)), 1)

            replay_payload = json.loads(replay.read_text(encoding="utf-8"))
            rows = replay_payload.get("observations") if isinstance(replay_payload.get("observations"), list) else []
            self.assertEqual(len(rows), 3)
            m3 = next(x for x in rows if x.get("mutation_id") == "m3")
            self.assertEqual(m3.get("observed_failure_type"), "semantic_regression")
            self.assertEqual(m3.get("label_match_expected"), True)

    def test_calibrator_needs_review_on_high_mismatch_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            raw = root / "raw.json"
            out = root / "summary.json"

            manifest.write_text(
                json.dumps({"mutations": [{"mutation_id": "m1", "expected_failure_type": "model_check_error"}]}),
                encoding="utf-8",
            )
            raw.write_text(
                json.dumps(
                    {
                        "schema_version": "mutation_raw_observations_v1",
                        "observations": [
                            {
                                "mutation_id": "m1",
                                "attempts": [{"return_code": 2, "timed_out": False, "stderr": "simulation failed in solver"}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_label_calibrator_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--raw-observations",
                    str(raw),
                    "--max-expected-mismatch-ratio-pct",
                    "10",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
            self.assertIn("expected_label_mismatch_ratio_high", summary.get("alerts", []))

    def test_calibrator_fails_when_required_input_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            out = root / "summary.json"
            manifest.write_text(json.dumps({"mutations": []}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_label_calibrator_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--raw-observations",
                    str(root / "missing_raw.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
