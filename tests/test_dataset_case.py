import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.dataset_case import load_dataset_case, validate_dataset_case


class DatasetCaseTests(unittest.TestCase):
    def test_validate_sample_case(self) -> None:
        payload = load_dataset_case("examples/datasets/dataset_case_example.json")
        validate_dataset_case(payload)

    def test_validate_fails_on_missing_required_key(self) -> None:
        payload = load_dataset_case("examples/datasets/dataset_case_example.json")
        payload.pop("actual_failure_type", None)
        with self.assertRaises(ValueError):
            validate_dataset_case(payload)

    def test_validate_fails_on_invalid_factor(self) -> None:
        payload = load_dataset_case("examples/datasets/dataset_case_example.json")
        payload["factors"]["root_cause"] = "bad_root_cause"
        with self.assertRaises(ValueError):
            validate_dataset_case(payload)

    def test_cli_validate_pass(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "gateforge.dataset_case_validate",
                "--in",
                "examples/datasets/dataset_case_example.json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout.strip())
        self.assertTrue(payload["valid"])

    def test_cli_validate_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            bad_path = Path(d) / "bad_case.json"
            bad_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "case_id": "bad-1"
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.dataset_case_validate", "--in", str(bad_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1, msg=proc.stderr or proc.stdout)
            payload = json.loads(proc.stdout.strip())
            self.assertFalse(payload["valid"])


if __name__ == "__main__":
    unittest.main()
