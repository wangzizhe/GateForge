import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationDepthPressureBoardV1Tests(unittest.TestCase):
    def test_pressure_board_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cov = root / "cov.json"
            aud = root / "aud.json"
            rec = root / "rec.json"
            out = root / "summary.json"

            cov.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "coverage_depth_score": 70.0,
                        "high_risk_gaps_count": 1,
                        "uncovered_cells_count": 2,
                        "high_risk_gaps": [
                            {
                                "model_scale": "large",
                                "failure_type": "simulate_error",
                                "stage": "simulate",
                                "missing_mutations": 2,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            aud.write_text(json.dumps({"status": "NEEDS_REVIEW", "missing_recipe_count": 2, "execution_coverage_pct": 60.0}), encoding="utf-8")
            rec.write_text(json.dumps({"status": "PASS", "high_priority_recipes": 3}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_depth_pressure_board_v1",
                    "--mutation-coverage-depth-summary",
                    str(cov),
                    "--mutation-recipe-execution-audit-summary",
                    str(aud),
                    "--modelica-mutation-recipe-library-summary",
                    str(rec),
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
            self.assertGreater(len(payload.get("backlog_tasks") or []), 0)

    def test_pressure_board_fail_when_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_depth_pressure_board_v1",
                    "--mutation-coverage-depth-summary",
                    str(root / "missing1.json"),
                    "--mutation-recipe-execution-audit-summary",
                    str(root / "missing2.json"),
                    "--modelica-mutation-recipe-library-summary",
                    str(root / "missing3.json"),
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


if __name__ == "__main__":
    unittest.main()
