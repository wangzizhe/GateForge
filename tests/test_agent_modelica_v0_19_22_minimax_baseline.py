from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_benchmark_trajectory_gf_v1 import _run_case  # noqa: E402


class V01922MiniMaxBaselineTests(unittest.TestCase):
    def test_run_case_planner_backend_override_wins_over_case_backend(self) -> None:
        case = {
            "task_id": "demo_case",
            "candidate_id": "demo_case",
            "failure_type": "constraint_violation",
            "expected_stage": "simulate",
            "source_model_path": "/tmp/source.mo",
            "mutated_model_path": "/tmp/mutated.mo",
            "planner_backend": "gemini",
            "backend": "openmodelica_docker",
        }

        captured: dict[str, list[str]] = {}

        def _fake_run(cmd: list[str], **kwargs):
            captured["cmd"] = list(cmd)
            out_path = Path(cmd[cmd.index("--out") + 1])
            out_path.write_text(json.dumps({"executor_status": "PASS", "attempts": []}), encoding="utf-8")

            class _Proc:
                returncode = 0
                stderr = ""

            return _Proc()

        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "case.json"
            with patch("run_benchmark_trajectory_gf_v1.subprocess.run", side_effect=_fake_run):
                payload = _run_case(case, out_path, planner_backend_override="auto")

        self.assertEqual(payload["executor_status"], "PASS")
        self.assertIn("--planner-backend", captured["cmd"])
        planner_backend = captured["cmd"][captured["cmd"].index("--planner-backend") + 1]
        self.assertEqual(planner_backend, "auto")


if __name__ == "__main__":
    unittest.main()
