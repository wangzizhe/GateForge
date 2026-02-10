import tempfile
import unittest
from pathlib import Path

from gateforge.core import run_pipeline


class SmokePipelineTests(unittest.TestCase):
    def test_mock_pipeline_writes_valid_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "evidence.json"
            evidence = run_pipeline(backend="mock", out_path=str(out))
            self.assertTrue(out.exists())
            self.assertEqual(evidence["status"], "success")
            self.assertEqual(evidence["gate"], "PASS")
            self.assertEqual(evidence["backend"], "mock")
            self.assertIsNone(evidence["model_script"])
            self.assertEqual(evidence["exit_code"], 0)
            self.assertIs(evidence["check_ok"], True)
            self.assertIs(evidence["simulate_ok"], True)

    def test_openmodelica_probe_never_crashes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "evidence.json"
            evidence = run_pipeline(backend="openmodelica", out_path=str(out))
            self.assertTrue(out.exists())
            self.assertIn(evidence["gate"], {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn("exit_code", evidence)
            self.assertIn("check_ok", evidence)
            self.assertIn("simulate_ok", evidence)

    def test_openmodelica_docker_probe_never_crashes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "evidence.json"
            evidence = run_pipeline(backend="openmodelica_docker", out_path=str(out))
            self.assertTrue(out.exists())
            self.assertIn(evidence["gate"], {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertEqual(evidence["model_script"], "examples/openmodelica/minimal_probe.mos")
            self.assertIn("exit_code", evidence)
            self.assertIn("check_ok", evidence)
            self.assertIn("simulate_ok", evidence)


if __name__ == "__main__":
    unittest.main()
