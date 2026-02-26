import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureCorpusRegistryTests(unittest.TestCase):
    def test_registry_pass_with_full_scale_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            catalog = root / "catalog.json"
            registry = root / "registry.json"
            out = root / "summary.json"
            catalog.write_text(
                json.dumps(
                    {
                        "cases": [
                            {"failure_type": "a", "model_scale": "small", "failure_stage": "s", "severity": "low"},
                            {"failure_type": "b", "model_scale": "medium", "failure_stage": "s", "severity": "medium"},
                            {"failure_type": "c", "model_scale": "large", "failure_stage": "s", "severity": "high"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_corpus_registry",
                    "--catalog",
                    str(catalog),
                    "--registry",
                    str(registry),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("missing_model_scales"), [])
            self.assertEqual(payload.get("duplicate_fingerprint_count"), 0)

    def test_registry_needs_review_on_duplicate_and_missing_scale(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            catalog = root / "catalog.json"
            registry = root / "registry.json"
            out = root / "summary.json"
            catalog.write_text(
                json.dumps(
                    [
                        {"failure_type": "solver_non_convergence", "model_scale": "small", "failure_stage": "simulation", "severity": "medium", "model_name": "M"},
                        {"failure_type": "solver_non_convergence", "model_scale": "small", "failure_stage": "simulation", "severity": "medium", "model_name": "M"},
                    ]
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_corpus_registry",
                    "--catalog",
                    str(catalog),
                    "--registry",
                    str(registry),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("duplicate_fingerprint_detected", payload.get("alerts", []))
            self.assertIn("model_scale_coverage_incomplete", payload.get("alerts", []))


if __name__ == "__main__":
    unittest.main()
