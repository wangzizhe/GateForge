import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelicaLibraryProvenanceGuardV1Tests(unittest.TestCase):
    def test_guard_passes_with_complete_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            out = root / "summary.json"

            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {
                                "model_id": "m1",
                                "source_path": "models/m1.mo",
                                "source_name": "source_a",
                                "license_tag": "MIT",
                                "checksum_sha256": "abc",
                                "reproducibility": {"om_version": "omc-1.25", "repro_command": "omc models/m1.mo"},
                            },
                            {
                                "model_id": "m2",
                                "source_path": "models/m2.mo",
                                "source_name": "source_b",
                                "license_tag": "Apache-2.0",
                                "checksum_sha256": "def",
                                "reproducibility": {"om_version": "omc-1.25", "repro_command": "omc models/m2.mo"},
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
                    "gateforge.dataset_modelica_library_provenance_guard_v1",
                    "--modelica-library-registry",
                    str(registry),
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

    def test_guard_needs_review_on_unknown_license_and_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            out = root / "summary.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {
                                "model_id": "m1",
                                "source_path": "models/m1.mo",
                                "source_name": "only_source",
                                "license_tag": "UNKNOWN",
                                "checksum_sha256": "abc",
                                "reproducibility": {"om_version": "", "repro_command": ""},
                            },
                            {
                                "model_id": "m2",
                                "source_path": "",
                                "source_name": "only_source",
                                "license_tag": "UNKNOWN",
                                "checksum_sha256": "",
                                "reproducibility": {"om_version": "omc-1.25", "repro_command": ""},
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
                    "gateforge.dataset_modelica_library_provenance_guard_v1",
                    "--modelica-library-registry",
                    str(registry),
                    "--max-unknown-license-ratio-pct",
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
            self.assertIn("unknown_license_ratio_above_threshold", summary.get("alerts", []))

    def test_guard_fails_when_registry_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_library_provenance_guard_v1",
                    "--modelica-library-registry",
                    str(root / "missing_registry.json"),
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
