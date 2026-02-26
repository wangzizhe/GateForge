import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureTaxonomyCoverageTests(unittest.TestCase):
    def test_coverage_pass_when_core_buckets_filled(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            catalog = root / "catalog.json"
            out = root / "summary.json"
            catalog.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "failure_type": "numerical_divergence",
                                "model_scale": "small",
                                "failure_stage": "compile",
                                "severity": "medium",
                            },
                            {
                                "failure_type": "solver_non_convergence",
                                "model_scale": "medium",
                                "failure_stage": "initialization",
                                "severity": "high",
                            },
                            {
                                "failure_type": "boundary_condition_drift",
                                "model_scale": "large",
                                "failure_stage": "simulation",
                                "severity": "critical",
                            },
                            {
                                "failure_type": "unit_parameter_mismatch",
                                "model_scale": "large",
                                "failure_stage": "postprocess",
                                "severity": "low",
                            },
                            {
                                "failure_type": "stability_regression",
                                "model_scale": "small",
                                "failure_stage": "simulation",
                                "severity": "medium",
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
                    "gateforge.dataset_failure_taxonomy_coverage",
                    "--catalog",
                    str(catalog),
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
            self.assertEqual(payload.get("missing_failure_types"), [])
            self.assertEqual(payload.get("missing_model_scales"), [])

    def test_coverage_needs_review_when_buckets_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            catalog = root / "catalog.json"
            out = root / "summary.json"
            catalog.write_text(
                json.dumps(
                    [
                        {
                            "failure_type": "numerical_divergence",
                            "model_scale": "small",
                            "failure_stage": "simulation",
                            "severity": "high",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_taxonomy_coverage",
                    "--catalog",
                    str(catalog),
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
            self.assertIn("failure_type_coverage_incomplete", payload.get("alerts", []))
            self.assertIn("model_scale_coverage_incomplete", payload.get("alerts", []))
            self.assertIn("stage_coverage_incomplete", payload.get("alerts", []))

    def test_coverage_fail_when_no_cases(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            catalog = root / "catalog.json"
            out = root / "summary.json"
            catalog.write_text(json.dumps({"cases": []}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_taxonomy_coverage",
                    "--catalog",
                    str(catalog),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")
            self.assertIn("failure_taxonomy_empty", payload.get("alerts", []))


if __name__ == "__main__":
    unittest.main()
