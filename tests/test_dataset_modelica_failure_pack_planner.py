import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelicaFailurePackPlannerTests(unittest.TestCase):
    def test_planner_builds_scale_targets(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            coverage = root / "coverage.json"
            ladder = root / "ladder.json"
            registry = root / "registry.json"
            out = root / "summary.json"

            coverage.write_text(
                json.dumps(
                    {
                        "plan": [
                            {
                                "plan_id": "coverage.plan.001",
                                "source_task_id": "blindspot.model_scale.large",
                                "priority": "P0",
                                "focus": "taxonomy_missing_model_scale",
                                "size_hint": "large",
                                "expected_moat_delta": 8.1,
                            },
                            {
                                "plan_id": "coverage.plan.002",
                                "source_task_id": "blindspot.failure_type.boundary_condition_drift",
                                "priority": "P1",
                                "focus": "taxonomy_missing_failure_type",
                                "size_hint": "medium",
                                "expected_moat_delta": 5.2,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            ladder.write_text(json.dumps({"scale_counts": {"small": 4, "medium": 1, "large": 0}}), encoding="utf-8")
            registry.write_text(json.dumps({"model_scale_counts": {"small": 10, "medium": 3, "large": 1}}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_failure_pack_planner",
                    "--failure-coverage-planner",
                    str(coverage),
                    "--model-scale-ladder",
                    str(ladder),
                    "--failure-corpus-registry-summary",
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
            self.assertGreaterEqual(int(payload.get("medium_target_new_cases", 0)), 1)
            self.assertGreaterEqual(int(payload.get("large_target_new_cases", 0)), 2)
            scales = [x.get("scale") for x in payload.get("scale_plan", [])]
            self.assertEqual(scales, ["large", "medium", "small"])

    def test_planner_fails_when_coverage_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_failure_pack_planner",
                    "--failure-coverage-planner",
                    str(root / "missing.json"),
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
            self.assertIn("failure_coverage_plan_missing", payload.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
