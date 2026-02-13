import os
import json
import subprocess
import sys
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
            self.assertIn("toolchain", evidence)
            self.assertEqual(evidence["toolchain"]["backend_name"], "mock")
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
            with temp_env(GATEFORGE_OM_SCRIPT="examples/openmodelica/minimal_probe.mos"):
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

    def test_smoke_cli_reads_mock_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            out = root / "evidence.json"
            proposal.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "proposal_id": "proposal-test-1",
                        "timestamp_utc": "2026-02-11T10:00:00Z",
                        "author_type": "human",
                        "backend": "mock",
                        "model_script": "examples/openmodelica/minimal_probe.mos",
                        "change_summary": "proposal-driven smoke",
                        "requested_actions": ["check", "simulate"],
                        "risk_level": "low",
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.smoke",
                    "--proposal",
                    str(proposal),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            evidence = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(evidence["backend"], "mock")
            self.assertEqual(evidence["gate"], "PASS")
            self.assertEqual(evidence["model_script"], "examples/openmodelica/minimal_probe.mos")
            self.assertEqual(evidence["proposal_id"], "proposal-test-1")


if __name__ == "__main__":
    unittest.main()
