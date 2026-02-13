import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RepairLoopTests(unittest.TestCase):
    def _write_fail_run_summary(self, path: Path, *, status: str = "FAIL", decision: str = "FAIL") -> None:
        path.write_text(
            json.dumps(
                {
                    "proposal_id": "proposal-fail-001",
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


if __name__ == "__main__":
    unittest.main()
