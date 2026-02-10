import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from gateforge.core import run_pipeline


@contextmanager
def temp_env(**changes: str):
    old = {k: os.environ.get(k) for k in changes}
    os.environ.update(changes)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class SmokePipelineTests(unittest.TestCase):
    def test_mock_pipeline_writes_valid_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "evidence.json"
            report = Path(d) / "evidence.md"
            evidence = run_pipeline(backend="mock", out_path=str(out))
            self.assertTrue(out.exists())
            self.assertTrue(report.exists())
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
            report = Path(d) / "evidence.md"
            evidence = run_pipeline(backend="openmodelica", out_path=str(out))
            self.assertTrue(out.exists())
            self.assertTrue(report.exists())
            self.assertIn(evidence["gate"], {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn("exit_code", evidence)
            self.assertIn("check_ok", evidence)
            self.assertIn("simulate_ok", evidence)

    def test_openmodelica_docker_probe_never_crashes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "evidence.json"
            report = Path(d) / "evidence.md"
            evidence = run_pipeline(backend="openmodelica_docker", out_path=str(out))
            self.assertTrue(out.exists())
            self.assertTrue(report.exists())
            self.assertIn(evidence["gate"], {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertEqual(evidence["model_script"], "examples/openmodelica/minimal_probe.mos")
            self.assertIn("exit_code", evidence)
            self.assertIn("check_ok", evidence)
            self.assertIn("simulate_ok", evidence)

    def test_failure_fixture_script_parse_error(self) -> None:
        with temp_env(GATEFORGE_OM_SCRIPT="examples/openmodelica/failures/script_parse_error.mos"):
            evidence = run_pipeline(backend="openmodelica_docker", out_path="artifacts/failure_script_parse.json")
        if evidence["failure_type"] in {"tool_missing", "docker_error"}:
            self.skipTest("Docker/OpenModelica unavailable in this environment")
        self.assertEqual(evidence["gate"], "FAIL")
        self.assertEqual(evidence["failure_type"], "script_parse_error")

    def test_failure_fixture_model_check_error(self) -> None:
        with temp_env(GATEFORGE_OM_SCRIPT="examples/openmodelica/failures/model_check_error.mos"):
            evidence = run_pipeline(backend="openmodelica_docker", out_path="artifacts/failure_model_check.json")
        if evidence["failure_type"] in {"tool_missing", "docker_error"}:
            self.skipTest("Docker/OpenModelica unavailable in this environment")
        self.assertEqual(evidence["gate"], "FAIL")
        self.assertEqual(evidence["failure_type"], "model_check_error")

    def test_failure_fixture_simulate_error(self) -> None:
        with temp_env(GATEFORGE_OM_SCRIPT="examples/openmodelica/failures/simulate_error.mos"):
            evidence = run_pipeline(backend="openmodelica_docker", out_path="artifacts/failure_simulate.json")
        if evidence["failure_type"] in {"tool_missing", "docker_error"}:
            self.skipTest("Docker/OpenModelica unavailable in this environment")
        self.assertEqual(evidence["gate"], "FAIL")
        self.assertEqual(evidence["failure_type"], "simulate_error")

    def test_custom_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "evidence.json"
            report = Path(d) / "custom-report.md"
            run_pipeline(backend="mock", out_path=str(out), report_path=str(report))
            self.assertTrue(out.exists())
            self.assertTrue(report.exists())


if __name__ == "__main__":
    unittest.main()
