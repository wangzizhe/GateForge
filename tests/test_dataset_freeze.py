import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFreezeTests(unittest.TestCase):
    def _write_dataset_jsonl(self, path: Path, n: int) -> None:
        rows = []
        for i in range(n):
            rows.append(json.dumps({"case_id": f"c{i}", "actual_failure_type": "none" if i % 2 == 0 else "simulate_error"}))
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def test_dataset_freeze_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            dataset = root / "dataset_cases.jsonl"
            distribution = root / "distribution.json"
            quality = root / "quality_report.json"
            out_dir = root / "freeze"
            self._write_dataset_jsonl(dataset, 20)
            distribution.write_text(json.dumps({"actual_failure_type": {"none": 10, "simulate_error": 10}}), encoding="utf-8")
            quality.write_text(json.dumps({"failure_case_rate": 0.5}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_freeze",
                    "--dataset-jsonl",
                    str(dataset),
                    "--distribution-json",
                    str(distribution),
                    "--quality-json",
                    str(quality),
                    "--freeze-id",
                    "freeze_v1_test",
                    "--out-dir",
                    str(out_dir),
                    "--min-cases",
                    "10",
                    "--min-failure-case-rate",
                    "0.2",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest.get("status"), "PASS")
            self.assertEqual(manifest.get("freeze_id"), "freeze_v1_test")
            self.assertIn("dataset_jsonl_sha256", manifest.get("checksums", {}))

    def test_dataset_freeze_fail_on_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            dataset = root / "dataset_cases.jsonl"
            distribution = root / "distribution.json"
            quality = root / "quality_report.json"
            out_dir = root / "freeze"
            self._write_dataset_jsonl(dataset, 5)
            distribution.write_text(json.dumps({"actual_failure_type": {"none": 5}}), encoding="utf-8")
            quality.write_text(json.dumps({"failure_case_rate": 0.0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_freeze",
                    "--dataset-jsonl",
                    str(dataset),
                    "--distribution-json",
                    str(distribution),
                    "--quality-json",
                    str(quality),
                    "--out-dir",
                    str(out_dir),
                    "--min-cases",
                    "10",
                    "--min-failure-case-rate",
                    "0.2",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            self.assertEqual(summary.get("gate_checks", {}).get("min_cases_check"), "FAIL")


if __name__ == "__main__":
    unittest.main()
