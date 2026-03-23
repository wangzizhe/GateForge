"""Unit tests for agent_modelica_compatibility_detector_v1.

All tests mock subprocess calls so Docker is NOT required.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from gateforge.agent_modelica_compatibility_detector_v1 import (
    CompatibilityReport,
    ProbeResult,
    SCHEMA_VERSION,
    _load_whitelist,
    _probe_docker_reachable,
    _probe_docker_image,
    _probe_msl_load,
    _probe_check_model,
    _probe_simulate,
    _run_whitelist_models,
    report_to_dict,
    run_compatibility_probes,
    write_compatibility_report,
)

_MODULE = "gateforge.agent_modelica_compatibility_detector_v1"
_EXECUTOR = "gateforge.agent_modelica_live_executor_gemini_v1"
_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"


class TestProbeDockerReachable(unittest.TestCase):
    """docker_reachable probe."""

    @patch(f"{_EXECUTOR}._run_cmd", return_value=(0, "27.0.3\n"))
    def test_pass(self, mock_cmd):
        r = _probe_docker_reachable()
        self.assertEqual(r.status, "pass")
        self.assertEqual(r.probe_id, "docker_reachable")
        self.assertIn("docker_version", r.metadata)
        self.assertGreaterEqual(r.latency_sec, 0.0)
        mock_cmd.assert_called_once()

    @patch(f"{_EXECUTOR}._run_cmd", return_value=(1, "Cannot connect to Docker daemon"))
    def test_fail(self, mock_cmd):
        r = _probe_docker_reachable()
        self.assertEqual(r.status, "fail")
        self.assertIn("Cannot connect", r.error_detail)

    @patch(f"{_EXECUTOR}._run_cmd", return_value=(0, ""))
    def test_fail_empty_output(self, mock_cmd):
        r = _probe_docker_reachable()
        self.assertEqual(r.status, "fail")


class TestProbeDockerImage(unittest.TestCase):
    """docker_image probe."""

    @patch(f"{_EXECUTOR}._run_cmd", return_value=(0, "sha256:abc123\n"))
    def test_pass_local(self, mock_cmd):
        r = _probe_docker_image(_IMAGE)
        self.assertEqual(r.status, "pass")
        self.assertFalse(r.metadata.get("pulled"))

    @patch(f"{_EXECUTOR}._run_cmd", side_effect=[
        (1, "No such image"),   # inspect fails
        (0, "Pull complete\n"),  # pull succeeds
    ])
    def test_pass_after_pull(self, mock_cmd):
        r = _probe_docker_image(_IMAGE)
        self.assertEqual(r.status, "pass")
        self.assertTrue(r.metadata.get("pulled"))
        self.assertEqual(mock_cmd.call_count, 2)

    @patch(f"{_EXECUTOR}._run_cmd", side_effect=[
        (1, "No such image"),
        (1, "pull failed: timeout"),
    ])
    def test_fail_pull(self, mock_cmd):
        r = _probe_docker_image(_IMAGE)
        self.assertEqual(r.status, "fail")


class TestProbeMslLoad(unittest.TestCase):
    """msl_load probe."""

    @patch(f"{_EXECUTOR}._run_omc_script_docker", return_value=(0, "true\n\"\"\n"))
    def test_pass(self, mock_omc):
        r = _probe_msl_load(_IMAGE)
        self.assertEqual(r.status, "pass")
        self.assertEqual(r.probe_id, "msl_load")

    @patch(f"{_EXECUTOR}._run_omc_script_docker",
           return_value=(0, 'false\n"Error: Modelica library not found"\n'))
    def test_fail_error_in_output(self, mock_omc):
        r = _probe_msl_load(_IMAGE)
        self.assertEqual(r.status, "fail")
        self.assertIn("Error", r.error_detail)

    @patch(f"{_EXECUTOR}._run_omc_script_docker", return_value=(1, ""))
    def test_fail_nonzero_exit(self, mock_omc):
        r = _probe_msl_load(_IMAGE)
        self.assertEqual(r.status, "fail")


class TestProbeCheckModel(unittest.TestCase):
    """check_model probe."""

    @patch(f"{_EXECUTOR}._extract_om_success_flags", return_value=(True, False))
    @patch(f"{_EXECUTOR}._run_omc_script_docker", return_value=(0, "Check of MinimalProbe completed successfully"))
    @patch(f"{_MODULE}._repo_root")
    def test_pass(self, mock_root, mock_omc, mock_flags):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            model_dir = root / "examples" / "openmodelica"
            model_dir.mkdir(parents=True)
            (model_dir / "MinimalProbe.mo").write_text("model MinimalProbe end MinimalProbe;")
            mock_root.return_value = root
            r = _probe_check_model(_IMAGE)
        self.assertEqual(r.status, "pass")
        self.assertEqual(r.probe_id, "check_model")

    @patch(f"{_MODULE}._repo_root")
    def test_fail_missing_model(self, mock_root):
        with tempfile.TemporaryDirectory() as td:
            mock_root.return_value = Path(td)
            r = _probe_check_model(_IMAGE)
        self.assertEqual(r.status, "fail")
        self.assertIn("not found", r.error_detail)

    @patch(f"{_EXECUTOR}._extract_om_success_flags", return_value=(False, False))
    @patch(f"{_EXECUTOR}._run_omc_script_docker", return_value=(0, "Error: type mismatch"))
    @patch(f"{_MODULE}._repo_root")
    def test_fail_check_fails(self, mock_root, mock_omc, mock_flags):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            model_dir = root / "examples" / "openmodelica"
            model_dir.mkdir(parents=True)
            (model_dir / "MinimalProbe.mo").write_text("model MinimalProbe end MinimalProbe;")
            mock_root.return_value = root
            r = _probe_check_model(_IMAGE)
        self.assertEqual(r.status, "fail")


class TestProbeSimulate(unittest.TestCase):
    """simulate probe."""

    @patch(f"{_EXECUTOR}._extract_om_success_flags", return_value=(False, True))
    @patch(f"{_EXECUTOR}._run_omc_script_docker", return_value=(0, "resultFile = ..."))
    @patch(f"{_MODULE}._repo_root")
    def test_pass(self, mock_root, mock_omc, mock_flags):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            model_dir = root / "examples" / "openmodelica"
            model_dir.mkdir(parents=True)
            (model_dir / "MinimalProbe.mo").write_text("model MinimalProbe end MinimalProbe;")
            mock_root.return_value = root
            r = _probe_simulate(_IMAGE)
        self.assertEqual(r.status, "pass")

    @patch(f"{_EXECUTOR}._extract_om_success_flags", return_value=(False, False))
    @patch(f"{_EXECUTOR}._run_omc_script_docker", return_value=(0, "Simulation failed"))
    @patch(f"{_MODULE}._repo_root")
    def test_fail(self, mock_root, mock_omc, mock_flags):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            model_dir = root / "examples" / "openmodelica"
            model_dir.mkdir(parents=True)
            (model_dir / "MinimalProbe.mo").write_text("model MinimalProbe end MinimalProbe;")
            mock_root.return_value = root
            r = _probe_simulate(_IMAGE)
        self.assertEqual(r.status, "fail")


class TestProbeChainShortCircuit(unittest.TestCase):
    """When Docker is unreachable, all downstream probes are skipped_dependency."""

    @patch(f"{_EXECUTOR}._run_cmd", return_value=(1, "daemon not running"))
    def test_docker_fail_skips_all(self, mock_cmd):
        report = run_compatibility_probes(_IMAGE, timeout_sec=30)
        self.assertEqual(report.overall_status, "fail")
        self.assertEqual(report.first_failure, "docker_reachable")
        self.assertEqual(len(report.probes), 5)
        # First probe failed, rest skipped.
        self.assertEqual(report.probes[0].status, "fail")
        for p in report.probes[1:]:
            self.assertEqual(p.status, "skipped_dependency", f"{p.probe_id} should be skipped")

    @patch(f"{_EXECUTOR}._run_omc_script_docker",
           return_value=(1, "MSL load failed catastrophically"))
    @patch(f"{_EXECUTOR}._run_cmd", side_effect=[
        (0, "27.0.3\n"),           # docker info
        (0, "sha256:abc123\n"),     # docker image inspect
    ])
    def test_msl_fail_skips_downstream(self, mock_cmd, mock_omc):
        report = run_compatibility_probes(_IMAGE, timeout_sec=30)
        self.assertEqual(report.overall_status, "fail")
        self.assertEqual(report.first_failure, "msl_load")
        statuses = {p.probe_id: p.status for p in report.probes}
        self.assertEqual(statuses["docker_reachable"], "pass")
        self.assertEqual(statuses["docker_image"], "pass")
        self.assertEqual(statuses["msl_load"], "fail")
        self.assertEqual(statuses["check_model"], "skipped_dependency")
        self.assertEqual(statuses["simulate"], "skipped_dependency")


class TestAllProbesPass(unittest.TestCase):
    """Happy path: every probe succeeds."""

    @patch(f"{_EXECUTOR}._extract_om_success_flags")
    @patch(f"{_EXECUTOR}._run_omc_script_docker")
    @patch(f"{_EXECUTOR}._run_cmd")
    @patch(f"{_MODULE}._repo_root")
    def test_all_pass(self, mock_root, mock_cmd, mock_omc, mock_flags):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            model_dir = root / "examples" / "openmodelica"
            model_dir.mkdir(parents=True)
            (model_dir / "MinimalProbe.mo").write_text("model MinimalProbe end MinimalProbe;")
            mock_root.return_value = root

            mock_cmd.return_value = (0, "27.0.3\n")
            # MSL load returns true, check/simulate return success text
            mock_omc.return_value = (0, "true\n\"\"\n")
            # check_model needs (True, _), simulate needs (_, True)
            mock_flags.side_effect = [(True, False), (False, True)]

            report = run_compatibility_probes(_IMAGE, timeout_sec=60)

        self.assertEqual(report.overall_status, "pass")
        self.assertEqual(report.first_failure, "")
        self.assertEqual(len(report.probes), 5)
        for p in report.probes:
            self.assertEqual(p.status, "pass", f"{p.probe_id} should pass")
        self.assertEqual(report.environment_failure_kinds, [])
        self.assertEqual(report.schema_version, SCHEMA_VERSION)


class TestEnvironmentFailureKinds(unittest.TestCase):
    """Verify that failure kinds map to the correct vocabulary."""

    @patch(f"{_EXECUTOR}._run_cmd", return_value=(1, "daemon not running"))
    def test_docker_failure_kind(self, mock_cmd):
        report = run_compatibility_probes(_IMAGE, timeout_sec=10)
        self.assertIn("docker_unavailable", report.environment_failure_kinds)

    @patch(f"{_EXECUTOR}._run_omc_script_docker",
           return_value=(1, "MSL not found"))
    @patch(f"{_EXECUTOR}._run_cmd", side_effect=[
        (0, "27.0.3\n"),
        (0, "sha256:abc\n"),
    ])
    def test_msl_failure_kind(self, mock_cmd, mock_omc):
        report = run_compatibility_probes(_IMAGE, timeout_sec=10)
        self.assertIn("modelica_package_unavailable", report.environment_failure_kinds)


class TestReportSerialization(unittest.TestCase):
    """JSON serialization round-trip."""

    def test_report_to_dict_roundtrip(self):
        report = CompatibilityReport(
            schema_version=SCHEMA_VERSION,
            run_id="test-run-01",
            timestamp_utc="2026-01-01T00:00:00.000000Z",
            docker_image=_IMAGE,
            overall_status="pass",
            first_failure="",
            total_latency_sec=1.5,
            probes=[
                ProbeResult(
                    probe_id="docker_reachable",
                    status="pass",
                    latency_sec=0.1,
                    timestamp_utc="2026-01-01T00:00:00.000000Z",
                    metadata={"docker_version": "27.0.3"},
                ),
            ],
            environment_failure_kinds=[],
        )
        d = report_to_dict(report)
        # Round-trip through JSON
        text = json.dumps(d)
        restored = json.loads(text)
        self.assertEqual(restored["schema_version"], SCHEMA_VERSION)
        self.assertEqual(restored["overall_status"], "pass")
        self.assertEqual(len(restored["probes"]), 1)
        self.assertEqual(restored["probes"][0]["probe_id"], "docker_reachable")

    def test_write_json_file(self):
        report = CompatibilityReport(
            schema_version=SCHEMA_VERSION,
            run_id="test-run-02",
            timestamp_utc="2026-01-01T00:00:00.000000Z",
            docker_image=_IMAGE,
            overall_status="fail",
            first_failure="msl_load",
            total_latency_sec=2.3,
            probes=[
                ProbeResult(
                    probe_id="msl_load",
                    status="fail",
                    latency_sec=1.2,
                    timestamp_utc="2026-01-01T00:00:00.000000Z",
                    error_detail="MSL not found",
                ),
            ],
            environment_failure_kinds=["modelica_package_unavailable"],
        )
        with tempfile.TemporaryDirectory() as td:
            json_path = str(Path(td) / "report.json")
            md_path = str(Path(td) / "report.md")
            write_compatibility_report(report, json_path, md_path)

            data = json.loads(Path(json_path).read_text())
            self.assertEqual(data["first_failure"], "msl_load")

            md = Path(md_path).read_text()
            self.assertIn("msl_load", md)
            self.assertIn("fail", md)


class TestWhitelist(unittest.TestCase):
    """Whitelist loading and model iteration."""

    def test_load_valid_whitelist(self):
        data = {
            "schema_version": "modelica_compatibility_whitelist_v1",
            "models": [
                {"model_id": "A", "model_path": "a.mo", "model_name": "A"},
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            models = _load_whitelist(f.name)
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["model_id"], "A")

    def test_load_missing_file(self):
        models = _load_whitelist("/nonexistent/path.json")
        self.assertEqual(models, [])

    @patch(f"{_EXECUTOR}._extract_om_success_flags", return_value=(True, True))
    @patch(f"{_EXECUTOR}._run_omc_script_docker", return_value=(0, "ok"))
    @patch(f"{_MODULE}._repo_root")
    def test_run_whitelist_models_pass(self, mock_root, mock_omc, mock_flags):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            model_dir = root / "examples" / "openmodelica"
            model_dir.mkdir(parents=True)
            (model_dir / "MinimalProbe.mo").write_text("model MinimalProbe end MinimalProbe;")
            mock_root.return_value = root

            models = [
                {
                    "model_id": "MinimalProbe",
                    "model_path": "examples/openmodelica/MinimalProbe.mo",
                    "model_name": "MinimalProbe",
                    "expect_check_pass": True,
                    "expect_simulate_pass": True,
                    "stop_time": 1.0,
                },
            ]
            results = _run_whitelist_models(models, _IMAGE, timeout_sec=30)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "pass")
        self.assertEqual(results[0].probe_id, "whitelist:MinimalProbe")

    @patch(f"{_MODULE}._repo_root")
    def test_run_whitelist_missing_model_file(self, mock_root):
        with tempfile.TemporaryDirectory() as td:
            mock_root.return_value = Path(td)
            models = [
                {
                    "model_id": "Ghost",
                    "model_path": "examples/openmodelica/Ghost.mo",
                    "model_name": "Ghost",
                },
            ]
            results = _run_whitelist_models(models, _IMAGE, timeout_sec=30)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "fail")
        self.assertIn("not found", results[0].error_detail)


class TestLatencyTracking(unittest.TestCase):
    """Every probe records a non-negative latency."""

    @patch(f"{_EXECUTOR}._run_cmd", return_value=(0, "27.0.3\n"))
    def test_positive_latency(self, mock_cmd):
        r = _probe_docker_reachable()
        self.assertGreaterEqual(r.latency_sec, 0.0)
        self.assertIsInstance(r.latency_sec, float)

    @patch(f"{_EXECUTOR}._run_cmd", return_value=(1, "fail"))
    def test_all_probes_have_latency(self, mock_cmd):
        report = run_compatibility_probes(_IMAGE, timeout_sec=10)
        for p in report.probes:
            self.assertGreaterEqual(p.latency_sec, 0.0)
            self.assertIsInstance(p.latency_sec, float)


class TestTimestampFields(unittest.TestCase):
    """Verify ISO 8601 timestamps are populated."""

    @patch(f"{_EXECUTOR}._run_cmd", return_value=(1, "fail"))
    def test_report_and_probes_have_timestamps(self, mock_cmd):
        report = run_compatibility_probes(_IMAGE, timeout_sec=10)
        self.assertTrue(report.timestamp_utc.endswith("Z"))
        for p in report.probes:
            self.assertTrue(p.timestamp_utc.endswith("Z"))


if __name__ == "__main__":
    unittest.main()
