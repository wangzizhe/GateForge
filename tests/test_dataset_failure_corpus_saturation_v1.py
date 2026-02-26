import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureCorpusSaturationV1Tests(unittest.TestCase):
    def test_saturation_needs_review_when_gaps_exist(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            db = root / "db.json"
            baseline = root / "baseline.json"
            out = root / "summary.json"

            db.write_text(
                json.dumps(
                    {
                        "schema_version": "failure_corpus_db_v1",
                        "cases": [
                            {"case_id": "c1", "failure_type": "simulate_error", "model_scale": "small"},
                            {"case_id": "c2", "failure_type": "simulate_error", "model_scale": "large"},
                            {"case_id": "c3", "failure_type": "model_check_error", "model_scale": "small"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            baseline.write_text(
                json.dumps(
                    {
                        "selected_cases": [
                            {"failure_type": "simulate_error"},
                            {"failure_type": "model_check_error"},
                            {"failure_type": "semantic_regression"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_corpus_saturation_v1",
                    "--failure-corpus-db",
                    str(db),
                    "--failure-baseline-pack",
                    str(baseline),
                    "--target-min-per-failure-type",
                    "3",
                    "--target-min-large-per-failure-type",
                    "1",
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
            self.assertGreater(int(summary.get("total_gap_actions", 0)), 0)

    def test_saturation_pass_when_targets_are_met(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            db = root / "db.json"
            baseline = root / "baseline.json"
            out = root / "summary.json"

            cases = []
            idx = 1
            for ft in ["simulate_error", "model_check_error", "semantic_regression", "numerical_instability", "constraint_violation"]:
                for scale in ["small", "medium", "large", "large"]:
                    cases.append({"case_id": f"c{idx}", "failure_type": ft, "model_scale": scale})
                    idx += 1
            db.write_text(json.dumps({"schema_version": "failure_corpus_db_v1", "cases": cases}), encoding="utf-8")
            baseline.write_text(
                json.dumps({"selected_cases": [{"failure_type": x} for x in ["simulate_error", "model_check_error", "semantic_regression"]]}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_corpus_saturation_v1",
                    "--failure-corpus-db",
                    str(db),
                    "--failure-baseline-pack",
                    str(baseline),
                    "--target-min-per-failure-type",
                    "3",
                    "--target-min-large-per-failure-type",
                    "2",
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
            self.assertEqual(int(summary.get("total_gap_actions", 0)), 0)

    def test_saturation_fails_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_corpus_saturation_v1",
                    "--failure-corpus-db",
                    str(root / "missing_db.json"),
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
