from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.run_non_ground_connect_deletion_qualification_v0_19_26 import _run_case


class TestV01930QualificationCommand(unittest.TestCase):
    def test_run_case_forwards_external_library_metadata(self):
        case = {
            "task_id": "case1",
            "failure_type": "model_check_error",
            "expected_stage": "check",
            "source_model_path": "/tmp/source.mo",
            "mutated_model_path": "/tmp/mutated.mo",
            "backend": "openmodelica_docker",
            "workflow_goal": "repair",
            "source_library_path": "/repo/Buildings",
            "source_package_name": "Buildings",
            "source_library_model_path": "/repo/Buildings/Controls/Continuous/Examples/LimPIDWithReset.mo",
            "source_qualified_model_name": "Buildings.Controls.Continuous.Examples.LimPIDWithReset",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.json"
            out_path.write_text(json.dumps({"attempts": [], "executor_status": "PASS"}), encoding="utf-8")
            seen_cmd = {}

            def _fake_run(cmd, capture_output, text, check, timeout, cwd):
                seen_cmd["cmd"] = list(cmd)
                return mock.Mock(returncode=0, stderr="")

            with mock.patch(
                "scripts.run_non_ground_connect_deletion_qualification_v0_19_26.subprocess.run",
                side_effect=_fake_run,
            ):
                payload = _run_case(case, out_path=out_path, planner_backend="auto")

        self.assertEqual(payload["executor_status"], "PASS")
        cmd = seen_cmd["cmd"]
        self.assertIn("--source-library-path", cmd)
        self.assertIn("/repo/Buildings", cmd)
        self.assertIn("--source-package-name", cmd)
        self.assertIn("Buildings", cmd)
        self.assertIn("--source-library-model-path", cmd)
        self.assertIn("/repo/Buildings/Controls/Continuous/Examples/LimPIDWithReset.mo", cmd)
        self.assertIn("--source-qualified-model-name", cmd)
        self.assertIn("Buildings.Controls.Continuous.Examples.LimPIDWithReset", cmd)


if __name__ == "__main__":
    unittest.main()
