import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetOpenSourceModelIntakeV1Tests(unittest.TestCase):
    def test_intake_accepts_allowed_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            catalog = root / "candidates.json"
            registry_out = root / "accepted.json"
            out = root / "summary.json"

            catalog.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "model_id": "m1",
                                "name": "A",
                                "source_url": "https://x/a",
                                "license": "MIT",
                                "scale_hint": "medium",
                                "repro_command": "omc a.mo",
                            },
                            {
                                "model_id": "m2",
                                "name": "B",
                                "source_url": "https://x/b",
                                "license": "Apache-2.0",
                                "scale_hint": "large",
                                "repro_command": "omc b.mo",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_open_source_model_intake_v1",
                    "--candidate-catalog",
                    str(catalog),
                    "--registry-out",
                    str(registry_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(int(summary.get("accepted_count", 0)), 2)

    def test_intake_rejects_partial_models_for_runnable_benchmarks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            catalog = root / "candidates.json"
            registry_out = root / "accepted.json"
            out = root / "summary.json"
            partial_model = root / "SMIBRenewable.mo"
            partial_model.write_text(
                "within OpenIPSL.Tests.BaseClasses;\n"
                "partial model SMIBRenewable\n"
                "end SMIBRenewable;\n",
                encoding="utf-8",
            )

            catalog.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "model_id": "m1",
                                "name": "SMIBRenewable",
                                "source_url": "local://OpenIPSL/Tests/BaseClasses/SMIBRenewable.mo",
                                "license": "BSD-3-Clause",
                                "scale_hint": "medium",
                                "repro_command": "omc SMIBRenewable.mo",
                                "local_path": str(partial_model),
                                "source_library_model_path": str(partial_model),
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_open_source_model_intake_v1",
                    "--candidate-catalog",
                    str(catalog),
                    "--registry-out",
                    str(registry_out),
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
            self.assertEqual(int(summary.get("accepted_count", 0)), 0)
            self.assertEqual(
                int((summary.get("rejection_reason_counts") or {}).get("partial_model_not_runnable", 0)),
                1,
            )

    def test_intake_fail_when_catalog_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_open_source_model_intake_v1",
                    "--candidate-catalog",
                    str(root / "missing.json"),
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
