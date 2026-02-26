import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureCoveragePlannerTests(unittest.TestCase):
    def test_planner_generates_prioritized_plan(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            backlog = root / "backlog.json"
            registry = root / "registry.json"
            moat = root / "moat.json"
            out = root / "summary.json"

            backlog.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "tasks": [
                            {
                                "task_id": "blindspot.model_scale.large",
                                "title": "Expand large coverage",
                                "reason": "taxonomy_missing_model_scale",
                                "priority": "P0",
                            },
                            {
                                "task_id": "blindspot.failure_type.numerical_divergence",
                                "title": "Add divergence cases",
                                "reason": "taxonomy_missing_failure_type",
                                "priority": "P1",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            registry.write_text(json.dumps({"missing_model_scales": ["large"]}), encoding="utf-8")
            moat.write_text(json.dumps({"metrics": {"moat_score": 54.2}}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_coverage_planner",
                    "--blind-spot-backlog",
                    str(backlog),
                    "--failure-corpus-registry-summary",
                    str(registry),
                    "--moat-trend-snapshot",
                    str(moat),
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
            self.assertGreaterEqual(int(payload.get("total_plan_items", 0)), 2)
            self.assertGreater(float(payload.get("expected_moat_delta_total", 0.0)), 0.0)
            plan = payload.get("plan") if isinstance(payload.get("plan"), list) else []
            self.assertTrue(plan)
            self.assertEqual(plan[0].get("priority"), "P0")

    def test_planner_fails_without_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_coverage_planner",
                    "--blind-spot-backlog",
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
            self.assertIn("backlog_missing", payload.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
