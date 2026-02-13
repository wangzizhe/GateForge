import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.regression import compare_evidence, write_json


def _evidence(
    run_id: str,
    schema_version: str = "0.1.0",
    backend: str = "mock",
    model_script: str | None = None,
    status: str = "success",
    gate: str = "PASS",
    check_ok: bool = True,
    simulate_ok: bool = True,
    runtime_seconds: float = 1.0,
    events: int = 10,
    proposal_id: str | None = None,
    failure_type: str = "none",
    log_excerpt: str = "",
    policy_version: str | None = "0.1.0",
) -> dict:
    return {
        "run_id": run_id,
        "proposal_id": proposal_id,
        "schema_version": schema_version,
        "backend": backend,
        "model_script": model_script,
        "status": status,
        "failure_type": failure_type,
        "gate": gate,
        "check_ok": check_ok,
        "simulate_ok": simulate_ok,
        "metrics": {"runtime_seconds": runtime_seconds, "events": events},
        "artifacts": {"log_excerpt": log_excerpt},
        "toolchain": {
            "backend_name": backend,
            "backend_version": "test",
            "docker_image": None,
            "policy_profile": "default",
            "policy_version": policy_version,
        },
        "policy_version": policy_version,
    }


class RegressionTests(unittest.TestCase):
    def test_compare_pass(self) -> None:
        baseline = _evidence("base", runtime_seconds=1.0, proposal_id="p-1")
        candidate = _evidence("cand", runtime_seconds=1.1, proposal_id="p-1")
        result = compare_evidence(baseline, candidate, runtime_regression_threshold=0.2)
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["proposal_id"], "p-1")
        self.assertEqual(result["reasons"], [])
        self.assertFalse(result["strict"])

    def test_compare_fail_runtime(self) -> None:
        baseline = _evidence("base", runtime_seconds=1.0)
        candidate = _evidence("cand", runtime_seconds=1.3)
        result = compare_evidence(baseline, candidate, runtime_regression_threshold=0.2)
        self.assertEqual(result["decision"], "FAIL")
        self.assertTrue(any(r.startswith("runtime_regression:") for r in result["reasons"]))

    def test_compare_fail_status(self) -> None:
        baseline = _evidence("base")
        candidate = _evidence("cand", status="failed", gate="FAIL", simulate_ok=False)
        result = compare_evidence(baseline, candidate, runtime_regression_threshold=0.2)
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("candidate_status_not_success", result["reasons"])

    def test_compare_fail_timeout_checker(self) -> None:
        baseline = _evidence("base")
        candidate = _evidence("cand", status="failed", gate="FAIL", failure_type="timeout")
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=0.2,
            checker_names=["timeout"],
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("timeout_detected", result["reasons"])
        self.assertTrue(any(f.get("checker") == "timeout" for f in result["findings"]))

    def test_compare_fail_nan_inf_checker(self) -> None:
        baseline = _evidence("base")
        candidate = _evidence(
            "cand",
            status="failed",
            gate="FAIL",
            failure_type="none",
            log_excerpt="solver produced NaN at t=0.5",
        )
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=0.2,
            checker_names=["nan_inf"],
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("nan_inf_detected", result["reasons"])
        self.assertTrue(any(f.get("checker") == "nan_inf" for f in result["findings"]))

    def test_compare_fail_performance_regression_checker(self) -> None:
        baseline = _evidence("base", runtime_seconds=1.0)
        candidate = _evidence("cand", runtime_seconds=2.5)
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=10.0,
            checker_names=["performance_regression"],
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("performance_regression_detected", result["reasons"])
        self.assertTrue(any(f.get("checker") == "performance_regression" for f in result["findings"]))

    def test_compare_fail_event_explosion_checker(self) -> None:
        baseline = _evidence("base", events=10)
        candidate = _evidence("cand", events=30)
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=10.0,
            checker_names=["event_explosion"],
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("event_explosion_detected", result["reasons"])
        self.assertTrue(any(f.get("checker") == "event_explosion" for f in result["findings"]))

    def test_compare_fail_performance_regression_checker_with_config(self) -> None:
        baseline = _evidence("base", runtime_seconds=1.0)
        candidate = _evidence("cand", runtime_seconds=1.6)
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=10.0,
            checker_names=["performance_regression"],
            checker_config={"performance_regression": {"max_ratio": 1.5}},
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("performance_regression_detected", result["reasons"])
        self.assertEqual(result["checker_config"]["performance_regression"]["max_ratio"], 1.5)

    def test_compare_fail_event_explosion_checker_with_config(self) -> None:
        baseline = _evidence("base", events=10)
        candidate = _evidence("cand", events=16)
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=10.0,
            checker_names=["event_explosion"],
            checker_config={"event_explosion": {"max_ratio": 1.5}},
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("event_explosion_detected", result["reasons"])
        self.assertEqual(result["checker_config"]["event_explosion"]["max_ratio"], 1.5)

    def test_compare_fail_steady_state_regression_checker(self) -> None:
        baseline = _evidence("base")
        candidate = _evidence("cand")
        baseline["metrics"]["steady_state_error"] = 0.02
        candidate["metrics"]["steady_state_error"] = 0.12
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=10.0,
            checker_names=["steady_state_regression"],
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("steady_state_regression_detected", result["reasons"])
        self.assertTrue(any(f.get("checker") == "steady_state_regression" for f in result["findings"]))

    def test_compare_runtime_checker_enable_disable(self) -> None:
        baseline = _evidence("base", runtime_seconds=1.0)
        candidate = _evidence("cand", runtime_seconds=1.6)
        result_disabled = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=10.0,
            checker_names=["performance_regression"],
            checker_config={"_runtime": {"disable": ["performance_regression"]}},
        )
        self.assertEqual(result_disabled["decision"], "PASS")
        result_enabled = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=10.0,
            checker_names=[],
            checker_config={
                "_runtime": {"enable": ["performance_regression"]},
                "performance_regression": {"max_ratio": 1.5},
            },
        )
        self.assertEqual(result_enabled["decision"], "FAIL")
        self.assertIn("performance_regression_detected", result_enabled["reasons"])

    def test_compare_fail_strict_backend_mismatch(self) -> None:
        baseline = _evidence("base", backend="mock")
        candidate = _evidence("cand", backend="openmodelica_docker")
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=0.2,
            strict=True,
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("strict_backend_mismatch", result["reasons"])

    def test_compare_fail_strict_schema_mismatch(self) -> None:
        baseline = _evidence("base", schema_version="0.1.0")
        candidate = _evidence("cand", schema_version="0.2.0")
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=0.2,
            strict=True,
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("strict_schema_version_mismatch", result["reasons"])

    def test_compare_fail_strict_model_script_mismatch(self) -> None:
        baseline = _evidence("base", model_script="examples/openmodelica/minimal_probe.mos")
        candidate = _evidence("cand", model_script="examples/openmodelica/failures/simulate_error.mos")
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=0.2,
            strict=True,
            strict_model_script=True,
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("strict_model_script_mismatch", result["reasons"])

    def test_compare_warn_strict_policy_version_mismatch(self) -> None:
        baseline = _evidence("base", policy_version="0.1.0")
        candidate = _evidence("cand", policy_version="0.2.0")
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=0.2,
            strict=True,
        )
        self.assertEqual(result["decision"], "PASS")
        self.assertIn("strict_policy_version_mismatch:0.1.0!=0.2.0", result["warnings"])

    def test_compare_fail_when_strict_policy_version_enabled(self) -> None:
        baseline = _evidence("base", policy_version="0.1.0")
        candidate = _evidence("cand", policy_version="0.2.0")
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=0.2,
            strict=True,
            strict_policy_version=True,
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("strict_policy_version_mismatch", result["reasons"])

    def test_write_json(self) -> None:
        payload = {"decision": "PASS", "reasons": []}
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "regression.json"
            write_json(str(out), payload)
            self.assertTrue(out.exists())

    def test_regress_cli_with_proposal_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            proposal = root / "proposal.json"
            out = root / "regression.json"

            payload = _evidence(
                "base",
                backend="mock",
                model_script="examples/openmodelica/minimal_probe.mos",
                runtime_seconds=1.0,
            )
            baseline.write_text(json.dumps(payload), encoding="utf-8")
            payload["run_id"] = "cand"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            proposal.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "proposal_id": "proposal-regress-1",
                        "timestamp_utc": "2026-02-11T10:00:00Z",
                        "author_type": "human",
                        "backend": "mock",
                        "model_script": "examples/openmodelica/minimal_probe.mos",
                        "change_summary": "proposal constrained regress",
                        "requested_actions": ["check", "regress"],
                        "risk_level": "low",
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.regress",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--proposal",
                    str(proposal),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["decision"], "PASS")
            self.assertEqual(result["proposal_id"], "proposal-regress-1")
            self.assertTrue(result["strict"])
            self.assertTrue(result["strict_model_script"])

    def test_regress_cli_with_proposal_fail_on_candidate_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            proposal = root / "proposal.json"
            out = root / "regression.json"

            baseline.write_text(
                json.dumps(
                    _evidence(
                        "base",
                        backend="mock",
                        model_script="examples/openmodelica/minimal_probe.mos",
                        runtime_seconds=1.0,
                    )
                ),
                encoding="utf-8",
            )
            candidate.write_text(
                json.dumps(
                    _evidence(
                        "cand",
                        backend="openmodelica_docker",
                        model_script="examples/openmodelica/failures/simulate_error.mos",
                        runtime_seconds=1.0,
                    )
                ),
                encoding="utf-8",
            )
            proposal.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "proposal_id": "proposal-regress-2",
                        "timestamp_utc": "2026-02-11T10:00:00Z",
                        "author_type": "human",
                        "backend": "mock",
                        "model_script": "examples/openmodelica/minimal_probe.mos",
                        "change_summary": "proposal mismatch test",
                        "requested_actions": ["check", "regress"],
                        "risk_level": "low",
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.regress",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--proposal",
                    str(proposal),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["decision"], "FAIL")
            self.assertIn("proposal_backend_mismatch_candidate", result["reasons"])
            self.assertIn("proposal_model_script_mismatch_candidate", result["reasons"])

    def test_regress_cli_with_proposal_runtime_low_risk_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            proposal = root / "proposal.json"
            out = root / "regression.json"

            baseline.write_text(
                json.dumps(
                    _evidence(
                        "base",
                        backend="mock",
                        model_script="examples/openmodelica/minimal_probe.mos",
                        runtime_seconds=1.0,
                    )
                ),
                encoding="utf-8",
            )
            candidate.write_text(
                json.dumps(
                    _evidence(
                        "cand",
                        backend="mock",
                        model_script="examples/openmodelica/minimal_probe.mos",
                        runtime_seconds=1.5,
                    )
                ),
                encoding="utf-8",
            )
            proposal.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "proposal_id": "proposal-regress-3",
                        "timestamp_utc": "2026-02-11T10:00:00Z",
                        "author_type": "human",
                        "backend": "mock",
                        "model_script": "examples/openmodelica/minimal_probe.mos",
                        "change_summary": "runtime drift low risk",
                        "requested_actions": ["check", "regress"],
                        "risk_level": "low",
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.regress",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--proposal",
                    str(proposal),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["decision"], "NEEDS_REVIEW")
            self.assertEqual(result["policy_decision"], "NEEDS_REVIEW")

    def test_regress_cli_with_proposal_runtime_high_risk_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            proposal = root / "proposal.json"
            out = root / "regression.json"

            baseline.write_text(
                json.dumps(
                    _evidence(
                        "base",
                        backend="mock",
                        model_script="examples/openmodelica/minimal_probe.mos",
                        runtime_seconds=1.0,
                    )
                ),
                encoding="utf-8",
            )
            candidate.write_text(
                json.dumps(
                    _evidence(
                        "cand",
                        backend="mock",
                        model_script="examples/openmodelica/minimal_probe.mos",
                        runtime_seconds=1.5,
                    )
                ),
                encoding="utf-8",
            )
            proposal.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "proposal_id": "proposal-regress-4",
                        "timestamp_utc": "2026-02-11T10:00:00Z",
                        "author_type": "human",
                        "backend": "mock",
                        "model_script": "examples/openmodelica/minimal_probe.mos",
                        "change_summary": "runtime drift high risk",
                        "requested_actions": ["check", "regress"],
                        "risk_level": "high",
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.regress",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--proposal",
                    str(proposal),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["decision"], "FAIL")
            self.assertEqual(result["policy_decision"], "FAIL")

    def test_regress_cli_with_proposal_uses_checker_config(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            proposal = root / "proposal.json"
            out = root / "regression.json"

            baseline.write_text(
                json.dumps(
                    _evidence(
                        "base",
                        backend="mock",
                        model_script="examples/openmodelica/minimal_probe.mos",
                        runtime_seconds=1.0,
                    )
                ),
                encoding="utf-8",
            )
            candidate.write_text(
                json.dumps(
                    _evidence(
                        "cand",
                        backend="mock",
                        model_script="examples/openmodelica/minimal_probe.mos",
                        runtime_seconds=1.0,
                        log_excerpt="NaN detected in state update",
                    )
                ),
                encoding="utf-8",
            )
            proposal.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "proposal_id": "proposal-regress-5",
                        "timestamp_utc": "2026-02-11T10:00:00Z",
                        "author_type": "human",
                        "backend": "mock",
                        "model_script": "examples/openmodelica/minimal_probe.mos",
                        "change_summary": "checker-config test",
                        "requested_actions": ["check", "regress"],
                        "risk_level": "low",
                        "checkers": ["nan_inf"],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.regress",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--proposal",
                    str(proposal),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("nan_inf_detected", result["reasons"])
            self.assertEqual(result["checkers"], ["nan_inf"])

    def test_regress_cli_uses_checker_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            checker_cfg = root / "checker_config.json"
            out = root / "regression.json"

            baseline.write_text(
                json.dumps(
                    _evidence(
                        "base",
                        backend="mock",
                        model_script="examples/openmodelica/minimal_probe.mos",
                        runtime_seconds=1.0,
                    )
                ),
                encoding="utf-8",
            )
            candidate.write_text(
                json.dumps(
                    _evidence(
                        "cand",
                        backend="mock",
                        model_script="examples/openmodelica/minimal_probe.mos",
                        runtime_seconds=1.6,
                    )
                ),
                encoding="utf-8",
            )
            checker_cfg.write_text(
                json.dumps({"performance_regression": {"max_ratio": 1.5}}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.regress",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--checker",
                    "performance_regression",
                    "--checker-config",
                    str(checker_cfg),
                    "--runtime-threshold",
                    "10",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("performance_regression_detected", result["reasons"])
            self.assertEqual(result["checker_config"]["performance_regression"]["max_ratio"], 1.5)

    def test_regress_cli_strict_policy_version_switch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            out_warn = root / "regression_warn.json"
            out_fail = root / "regression_fail.json"

            baseline.write_text(json.dumps(_evidence("base", policy_version="0.1.0")), encoding="utf-8")
            candidate.write_text(json.dumps(_evidence("cand", policy_version="0.2.0")), encoding="utf-8")

            proc_warn = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.regress",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--strict",
                    "--out",
                    str(out_warn),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_warn.returncode, 0, msg=proc_warn.stderr or proc_warn.stdout)
            warn_payload = json.loads(out_warn.read_text(encoding="utf-8"))
            self.assertEqual(warn_payload["decision"], "PASS")
            self.assertTrue(warn_payload.get("warnings"))

            proc_fail = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.regress",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--strict",
                    "--strict-policy-version",
                    "--out",
                    str(out_fail),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc_fail.returncode, 0)
            fail_payload = json.loads(out_fail.read_text(encoding="utf-8"))
            self.assertEqual(fail_payload["decision"], "FAIL")
            self.assertIn("strict_policy_version_mismatch", fail_payload["reasons"])


if __name__ == "__main__":
    unittest.main()
