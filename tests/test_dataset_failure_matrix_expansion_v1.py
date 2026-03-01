import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureMatrixExpansionV1Tests(unittest.TestCase):
    def test_expansion_tasks_generated(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            matrix = root / "matrix.json"
            out = root / "summary.json"
            matrix.write_text(
                json.dumps(
                    {
                        "matrix_coverage_score": 78.0,
                        "high_risk_uncovered_cells": 2,
                        "top_10_gap_plan": [
                            {
                                "model_scale": "large",
                                "failure_type": "solver_non_convergence",
                                "mutation_method": "equation_flip",
                                "missing": 2,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_matrix_expansion_v1",
                    "--mutation-coverage-matrix-summary",
                    str(matrix),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertGreaterEqual(payload.get("planned_expansion_tasks", 0), 1)


if __name__ == "__main__":
    unittest.main()
