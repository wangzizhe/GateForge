import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RepairLoopTests(unittest.TestCase):
    def _write_fail_run_summary(
        self,
        path: Path,
        *,
        status: str = "FAIL",
        decision: str = "FAIL",
        risk_level: str = "low",
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "proposal_id": "proposal-fail-001",
                    "risk_level": risk_level,
                    "status": status,
                    "policy_decision": decision,
                    "policy_reasons": ["runtime_regression:1.2s>1.0s"],
                    "fail_reasons": ["regression_fail"],
                }
            ),
            encoding="utf-8",
        )

    def _write_baseline(self, path: Path, backend: str = "mock") -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": "baseline-repair-loop-1",
                    "backend": backend,
                    "model_script": "examples/openmodelica/minimal_probe.mos",
                    "status": "success",
                    "gate": "PASS",
                    "check_ok": True,
                    "simulate_ok": True,
                    "metrics": {"runtime_seconds": 0.1},
                }
            ),
            encoding="utf-8",
        )

    def test_repair_loop_rule_improves_fail_to_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source_fail.json"
            baseline = root / "baseline.json"
            out = root / "repair_summary.json"
            self._write_fail_run_summary(source, status="FAIL", decision="FAIL")
            self._write_baseline(baseline, backend="mock")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_loop",
                    "--source",
                    str(source),
                    "--planner-backend",
                    "rule",
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["before"]["policy_decision"], "FAIL")
            self.assertEqual(payload["after"]["status"], "PASS")
            self.assertEqual(payload["comparison"]["delta"], "improved")
            self.assertEqual(payload.get("before_status"), "FAIL")
            self.assertEqual(payload.get("after_status"), "PASS")
            self.assertFalse(payload.get("safety_guard_triggered"))

    def test_repair_loop_gemini_requires_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source_fail.json"
            baseline = root / "baseline.json"
            out = root / "repair_summary_gemini.json"
            self._write_fail_run_summary(source, status="FAIL", decision="FAIL")
            self._write_baseline(baseline, backend="mock")

            env = dict(os.environ)
            had_key = bool(env.get("GOOGLE_API_KEY"))
            if had_key:
                env["GOOGLE_API_KEY"] = ""
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_loop",
                    "--source",
                    str(source),
                    "--planner-backend",
                    "gemini",
                    "--no-retry-on-failed-attempt",
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("autopilot_stderr_tail", payload)
            self.assertEqual(payload["after"]["autopilot_exit_code"], proc.returncode)
            self.assertIn(payload["after"]["status"], {"UNKNOWN", "FAIL"})
            self.assertEqual(payload.get("planner_guardrail_decision"), "FAIL")
            self.assertTrue(payload.get("planner_guardrail_violations"))

    def test_repair_loop_retry_fallback_rule_recovers_from_gemini_failure(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source_fail.json"
            baseline = root / "baseline.json"
            out = root / "repair_summary_retry.json"
            self._write_fail_run_summary(source, status="FAIL", decision="FAIL")
            self._write_baseline(baseline, backend="mock")

            env = dict(os.environ)
            had_key = bool(env.get("GOOGLE_API_KEY"))
            if had_key:
                env["GOOGLE_API_KEY"] = ""

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_loop",
                    "--source",
                    str(source),
                    "--planner-backend",
                    "gemini",
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(payload.get("retry_used"))
            self.assertGreaterEqual(len(payload.get("attempts", [])), 2)
            self.assertEqual(payload.get("status"), "PASS")
            self.assertIn("retry_analysis", payload)
            self.assertTrue(payload["retry_analysis"].get("recovered_by_retry"))

    def test_repair_loop_max_retries_zero_disables_retry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source_fail.json"
            baseline = root / "baseline.json"
            out = root / "repair_summary_no_retry.json"
            self._write_fail_run_summary(source, status="FAIL", decision="FAIL")
            self._write_baseline(baseline, backend="mock")

            env = dict(os.environ)
            env.pop("GOOGLE_API_KEY", None)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_loop",
                    "--source",
                    str(source),
                    "--planner-backend",
                    "gemini",
                    "--max-retries",
                    "0",
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertFalse(payload.get("retry_used"))
            self.assertEqual(len(payload.get("attempts", [])), 1)
            self.assertEqual(payload.get("max_retries"), 0)

    def test_repair_loop_detects_worse_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source_pass.json"
            baseline = root / "baseline_mismatch.json"
            out = root / "repair_summary_worse.json"
            self._write_fail_run_summary(source, status="PASS", decision="PASS")
            self._write_baseline(baseline, backend="openmodelica_docker")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_loop",
                    "--source",
                    str(source),
                    "--planner-backend",
                    "rule",
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["before"]["policy_decision"], "PASS")
            self.assertEqual(payload["after"]["policy_decision"], "FAIL")
            self.assertEqual(payload["comparison"]["delta"], "worse")

    def test_repair_loop_blocks_new_critical_reason(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source_pass.json"
            baseline = root / "baseline_mismatch.json"
            out = root / "repair_summary_safety.json"
            self._write_fail_run_summary(source, status="PASS", decision="PASS")
            self._write_baseline(baseline, backend="openmodelica_docker")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_loop",
                    "--source",
                    str(source),
                    "--planner-backend",
                    "rule",
                    "--baseline",
                    str(baseline),
                    "--block-new-reason-prefix",
                    "strict_",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(payload.get("safety_guard_triggered"))
            self.assertEqual(payload.get("after", {}).get("status"), "FAIL")
            self.assertTrue(
                any(
                    str(r).startswith("repair_safety_new_critical_reason:")
                    for r in payload.get("after", {}).get("reasons", [])
                )
            )

    def test_repair_loop_risk_based_budget_high_disables_retry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source_high_risk.json"
            baseline = root / "baseline.json"
            out = root / "repair_summary_high_risk.json"
            self._write_fail_run_summary(source, status="FAIL", decision="FAIL", risk_level="high")
            self._write_baseline(baseline, backend="mock")

            env = dict(os.environ)
            env.pop("GOOGLE_API_KEY", None)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_loop",
                    "--source",
                    str(source),
                    "--planner-backend",
                    "gemini",
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("source_risk_level"), "high")
            self.assertEqual(payload.get("max_retries"), 0)
            self.assertEqual(payload.get("retry_budget_source"), "risk_based:high")
            self.assertEqual(len(payload.get("attempts", [])), 1)

    def test_repair_loop_auto_invariant_repair_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source_invariant_fail.json"
            baseline = root / "baseline.json"
            out = root / "repair_summary_invariant.json"
            source.write_text(
                json.dumps(
                    {
                        "proposal_id": "proposal-invariant-001",
                        "risk_level": "high",
                        "status": "FAIL",
                        "policy_decision": "FAIL",
                        "policy_reasons": ["physical_invariant_range_violated:steady_state_error"],
                        "checker_config": {
                            "invariant_guard": {
                                "invariants": [
                                    {"type": "range", "metric": "steady_state_error", "min": 0.0, "max": 0.08}
                                ]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            self._write_baseline(baseline, backend="mock")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_loop",
                    "--source",
                    str(source),
                    "--planner-backend",
                    "rule",
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(payload.get("invariant_repair_detected"))
            self.assertTrue(payload.get("invariant_repair_applied"))
            self.assertGreaterEqual(payload.get("invariant_repair_reason_count", 0), 1)
            self.assertIn("examples/openmodelica/MinimalProbe.mo", payload.get("planner_change_plan_allowed_files", []))
            self.assertEqual(payload.get("invariant_repair_profile"), "default")
            self.assertEqual(payload.get("invariant_repair_profile_version"), "0.1.0")

    def test_repair_loop_invariant_profile_strict(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source_invariant_fail.json"
            baseline = root / "baseline.json"
            out = root / "repair_summary_invariant_strict.json"
            source.write_text(
                json.dumps(
                    {
                        "proposal_id": "proposal-invariant-002",
                        "risk_level": "high",
                        "status": "FAIL",
                        "policy_decision": "FAIL",
                        "policy_reasons": ["physical_invariant_range_violated:steady_state_error"],
                    }
                ),
                encoding="utf-8",
            )
            self._write_baseline(baseline, backend="mock")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_loop",
                    "--source",
                    str(source),
                    "--planner-backend",
                    "rule",
                    "--invariant-repair-profile",
                    "industrial_strict",
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertIn(proc.returncode, {0, 1}, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("invariant_repair_profile"), "industrial_strict")
            self.assertEqual(payload.get("invariant_repair_profile_version"), "0.1.0-industrial")
            self.assertGreaterEqual(float(payload.get("planner_change_plan_confidence_min", 0.0)), 0.92)


if __name__ == "__main__":
    unittest.main()
