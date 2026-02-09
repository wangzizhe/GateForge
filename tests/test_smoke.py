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

    def test_openmodelica_probe_never_crashes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "evidence.json"
            evidence = run_pipeline(backend="openmodelica", out_path=str(out))
            self.assertTrue(out.exists())
            self.assertIn(evidence["gate"], {"PASS", "NEEDS_REVIEW", "FAIL"})


if __name__ == "__main__":
    unittest.main()

