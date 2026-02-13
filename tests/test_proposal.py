import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.proposal import load_proposal, validate_proposal
from gateforge.proposal import execution_target_from_proposal


class ProposalTests(unittest.TestCase):
    def test_validate_sample_proposal(self) -> None:
        proposal = load_proposal("examples/proposals/proposal_v0.json")
        validate_proposal(proposal)

    def test_validate_fails_on_missing_key(self) -> None:
        proposal = {
            "schema_version": "0.1.0",
            "proposal_id": "p1",
            "timestamp_utc": "2026-02-11T10:00:00Z",
            "author_type": "human",
            "backend": "mock",
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "change_summary": "test",
            "requested_actions": ["check"],
        }
        with self.assertRaises(ValueError):
            validate_proposal(proposal)

    def test_validate_fails_on_bad_action(self) -> None:
        proposal = {
            "schema_version": "0.1.0",
            "proposal_id": "p1",
            "timestamp_utc": "2026-02-11T10:00:00Z",
            "author_type": "human",
            "backend": "mock",
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "change_summary": "test",
            "requested_actions": ["unknown_action"],
            "risk_level": "low",
        }
        with self.assertRaises(ValueError):
            validate_proposal(proposal)

    def test_cli_validate_pass(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "gateforge.proposal_validate",
                "--in",
                "examples/proposals/proposal_v0.json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout.strip())
        self.assertTrue(payload["valid"])

    def test_cli_validate_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            bad_path = Path(d) / "bad_proposal.json"
            bad_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "proposal_id": "bad",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.proposal_validate", "--in", str(bad_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(proc.stdout.strip())
            self.assertFalse(payload["valid"])

    def test_execution_target_requires_check_or_simulate(self) -> None:
        proposal = {
            "schema_version": "0.1.0",
            "proposal_id": "p2",
            "timestamp_utc": "2026-02-11T10:00:00Z",
            "author_type": "human",
            "backend": "mock",
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "change_summary": "regression-only request",
            "requested_actions": ["regress"],
            "risk_level": "low",
        }
        with self.assertRaises(ValueError):
            execution_target_from_proposal(proposal)

    def test_validate_accepts_optional_change_set_path(self) -> None:
        proposal = {
            "schema_version": "0.1.0",
            "proposal_id": "p3",
            "timestamp_utc": "2026-02-11T10:00:00Z",
            "author_type": "human",
            "backend": "mock",
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "change_summary": "proposal with deterministic change set",
            "requested_actions": ["check", "simulate"],
            "risk_level": "low",
            "change_set_path": "examples/changesets/minimalprobe_x_to_2.json",
        }
        validate_proposal(proposal)

    def test_validate_accepts_optional_checkers(self) -> None:
        proposal = {
            "schema_version": "0.1.0",
            "proposal_id": "p4",
            "timestamp_utc": "2026-02-11T10:00:00Z",
            "author_type": "human",
            "backend": "mock",
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "change_summary": "proposal with explicit checker config",
            "requested_actions": ["check", "regress"],
            "risk_level": "low",
            "checkers": ["timeout", "nan_inf"],
        }
        validate_proposal(proposal)

    def test_validate_fails_on_unknown_checker(self) -> None:
        proposal = {
            "schema_version": "0.1.0",
            "proposal_id": "p5",
            "timestamp_utc": "2026-02-11T10:00:00Z",
            "author_type": "human",
            "backend": "mock",
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "change_summary": "proposal with bad checker",
            "requested_actions": ["check", "regress"],
            "risk_level": "low",
            "checkers": ["unknown_checker"],
        }
        with self.assertRaises(ValueError):
            validate_proposal(proposal)

    def test_validate_accepts_checker_config(self) -> None:
        proposal = {
            "schema_version": "0.1.0",
            "proposal_id": "p6",
            "timestamp_utc": "2026-02-11T10:00:00Z",
            "author_type": "human",
            "backend": "mock",
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "change_summary": "proposal with checker_config",
            "requested_actions": ["check", "regress"],
            "risk_level": "low",
            "checkers": ["performance_regression", "event_explosion"],
            "checker_config": {
                "performance_regression": {"max_ratio": 1.5},
                "event_explosion": {"max_ratio": 1.4, "abs_threshold_if_baseline_zero": 50},
            },
        }
        validate_proposal(proposal)

    def test_validate_fails_on_invalid_checker_config(self) -> None:
        proposal = {
            "schema_version": "0.1.0",
            "proposal_id": "p7",
            "timestamp_utc": "2026-02-11T10:00:00Z",
            "author_type": "human",
            "backend": "mock",
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "change_summary": "proposal with invalid checker_config",
            "requested_actions": ["check", "regress"],
            "risk_level": "low",
            "checkers": ["performance_regression"],
            "checker_config": {
                "performance_regression": {"max_ratio": 0},
            },
        }
        with self.assertRaises(ValueError):
            validate_proposal(proposal)

    def test_validate_fails_on_invalid_steady_state_checker_config(self) -> None:
        proposal = {
            "schema_version": "0.1.0",
            "proposal_id": "proposal-invalid-steady-1",
            "timestamp_utc": "2026-02-12T00:00:00Z",
            "author_type": "human",
            "backend": "mock",
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "change_summary": "invalid steady-state checker config",
            "requested_actions": ["check", "regress"],
            "risk_level": "low",
            "checkers": ["steady_state_regression"],
            "checker_config": {
                "steady_state_regression": {"max_abs_delta": 0}
            },
        }
        with self.assertRaises(ValueError):
            validate_proposal(proposal)

    def test_validate_accepts_runtime_checker_toggle_config(self) -> None:
        proposal = {
            "schema_version": "0.1.0",
            "proposal_id": "proposal-runtime-cfg-1",
            "timestamp_utc": "2026-02-13T00:00:00Z",
            "author_type": "human",
            "backend": "mock",
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "change_summary": "runtime checker toggles",
            "requested_actions": ["check", "regress"],
            "risk_level": "medium",
            "checker_config": {
                "_runtime": {
                    "enable": ["steady_state_regression"],
                    "disable": ["performance_regression"],
                }
            },
        }
        validate_proposal(proposal)

    def test_validate_fails_on_runtime_checker_toggle_unknown_checker(self) -> None:
        proposal = {
            "schema_version": "0.1.0",
            "proposal_id": "proposal-runtime-cfg-2",
            "timestamp_utc": "2026-02-13T00:00:00Z",
            "author_type": "human",
            "backend": "mock",
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "change_summary": "runtime checker toggles bad checker",
            "requested_actions": ["check", "regress"],
            "risk_level": "medium",
            "checker_config": {
                "_runtime": {
                    "enable": ["not_a_checker"]
                }
            },
        }
        with self.assertRaises(ValueError):
            validate_proposal(proposal)


if __name__ == "__main__":
    unittest.main()
