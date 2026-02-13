import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AutopilotTests(unittest.TestCase):
    def _write_baseline(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": "base-autopilot-1",
                    "backend": "mock",
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

    def _write_mismatch_baseline(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": "base-autopilot-mismatch-1",
                    "backend": "openmodelica_docker",
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

    def test_autopilot_goal_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            intent_out = root / "intent.json"
            agent_run_out = root / "agent_run.json"
            out = root / "summary.json"
            report = root / "summary.md"
            self._write_baseline(baseline)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "run demo mock pass",
                    "--proposal-id",
                    "autopilot-test-1",
                    "--baseline",
                    str(baseline),
                    "--intent-out",
                    str(intent_out),
                    "--agent-run-out",
                    str(agent_run_out),
                    "--out",
                    str(out),
                    "--report",
                    str(report),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["proposal_id"], "autopilot-test-1")
            self.assertEqual(payload["intent"], "demo_mock_pass")
            self.assertEqual(payload["save_run_under"], "autopilot")
            self.assertEqual(payload["planner_backend"], "rule")
            self.assertFalse(payload["materialize_change_set"])
            self.assertEqual(payload["planner_exit_code"], 0)
            self.assertEqual(payload["agent_run_exit_code"], 0)
            self.assertEqual(payload["policy_version"], "0.1.0")
            self.assertEqual(payload["policy_decision"], "PASS")
            self.assertEqual(payload["policy_reasons"], [])
            self.assertEqual(payload["required_human_checks"], [])
            self.assertEqual(payload["change_apply_status"], "not_requested")
            self.assertEqual(payload["change_set_hash"], None)
            self.assertEqual(payload["applied_changes_count"], 0)
            self.assertIn("run_report_path", payload)
            self.assertEqual(payload["run_path"], "artifacts/autopilot/run_summary.json")
            self.assertEqual(payload["run_report_path"], "artifacts/autopilot/run_summary.md")
            self.assertTrue(report.exists())
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# GateForge Autopilot Summary", report_text)
            self.assertIn("## Required Human Checks", report_text)

    def test_autopilot_context_json_propagates_to_intent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            intent_out = root / "intent.json"
            agent_run_out = root / "agent_run.json"
            out = root / "summary.json"
            context = root / "context.json"
            self._write_baseline(baseline)
            context.write_text(
                json.dumps(
                    {
                        "risk_level": "medium",
                        "change_summary": "context override in autopilot",
                        "checkers": ["steady_state_regression"],
                        "checker_config": {
                            "steady_state_regression": {"max_abs_delta": 0.05}
                        },
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "run demo mock pass",
                    "--proposal-id",
                    "autopilot-test-2",
                    "--baseline",
                    str(baseline),
                    "--context-json",
                    str(context),
                    "--intent-out",
                    str(intent_out),
                    "--agent-run-out",
                    str(agent_run_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["planner_backend"], "rule")
            self.assertFalse(payload["materialize_change_set"])
            self.assertEqual(payload["checkers"], ["steady_state_regression"])
            self.assertEqual(
                payload["checker_config"]["steady_state_regression"]["max_abs_delta"],
                0.05,
            )
            intent_payload = json.loads(intent_out.read_text(encoding="utf-8"))
            self.assertEqual(intent_payload["overrides"]["risk_level"], "medium")
            self.assertEqual(intent_payload["overrides"]["change_summary"], "context override in autopilot")
            self.assertEqual(intent_payload["overrides"]["checkers"], ["steady_state_regression"])

    def test_autopilot_fail_on_baseline_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline_mismatch.json"
            out = root / "summary.json"
            self._write_mismatch_baseline(baseline)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "run demo mock pass",
                    "--proposal-id",
                    "autopilot-test-fail-1",
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
            self.assertEqual(payload["status"], "FAIL")
            self.assertEqual(payload["planner_backend"], "rule")
            self.assertFalse(payload["materialize_change_set"])
            self.assertEqual(payload["policy_decision"], "FAIL")
            self.assertTrue(payload["fail_reasons"])
            self.assertTrue(payload["policy_reasons"])
            self.assertTrue(payload["required_human_checks"])
            self.assertEqual(payload["change_apply_status"], "not_requested")
            self.assertEqual(payload["change_set_hash"], None)
            self.assertEqual(payload["applied_changes_count"], 0)
            self.assertIn("run_report_path", payload)

    def test_autopilot_save_run_under_agent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            out = root / "summary.json"
            self._write_baseline(baseline)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "run demo mock pass",
                    "--proposal-id",
                    "autopilot-test-agent-root-1",
                    "--baseline",
                    str(baseline),
                    "--save-run-under",
                    "agent",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["save_run_under"], "agent")
            self.assertEqual(payload["planner_backend"], "rule")
            self.assertFalse(payload["materialize_change_set"])
            self.assertEqual(payload["change_apply_status"], "not_requested")
            self.assertEqual(payload["change_set_hash"], None)
            self.assertEqual(payload["applied_changes_count"], 0)
            self.assertEqual(payload["run_path"], "artifacts/agent/run_summary.json")
            self.assertEqual(payload["run_report_path"], "artifacts/agent/run_summary.md")

    def test_autopilot_dry_run_plans_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            report = root / "summary.md"
            intent_out = root / "intent.json"
            agent_run_out = root / "agent_run.json"

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "run demo mock pass",
                    "--proposal-id",
                    "autopilot-dry-run-1",
                    "--dry-run",
                    "--intent-out",
                    str(intent_out),
                    "--agent-run-out",
                    str(agent_run_out),
                    "--out",
                    str(out),
                    "--report",
                    str(report),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "PLANNED")
            self.assertEqual(payload["planner_backend"], "rule")
            self.assertFalse(payload["materialize_change_set"])
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["agent_run_exit_code"], None)
            self.assertEqual(payload["proposal_id"], "autopilot-dry-run-1")
            self.assertIn("planned_run", payload)
            self.assertEqual(payload["planned_risk_level"], "low")
            self.assertTrue(payload["planned_required_human_checks"])
            self.assertEqual(payload["planned_run"]["run_out"], "artifacts/autopilot/run_summary.json")
            self.assertFalse(agent_run_out.exists())
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("PLANNED", report_text)
            self.assertIn("## Planned Human Checks (Dry Run)", report_text)

    def test_autopilot_dry_run_high_risk_planned_checks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            context = root / "context.json"
            context.write_text(
                json.dumps(
                    {
                        "risk_level": "high",
                        "change_summary": "high risk dry run",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "run demo mock pass",
                    "--context-json",
                    str(context),
                    "--dry-run",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "PLANNED")
            self.assertEqual(payload["planned_risk_level"], "high")
            checks = payload.get("planned_required_human_checks", [])
            self.assertTrue(any("rollback" in c.lower() for c in checks))

    def test_autopilot_dry_run_uses_policy_templates(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            context = root / "context.json"
            policy = root / "policy.json"
            context.write_text(
                json.dumps(
                    {
                        "risk_level": "high",
                        "change_summary": "high risk dry run with custom policy",
                    }
                ),
                encoding="utf-8",
            )
            policy.write_text(
                json.dumps(
                    {
                        "critical_reason_prefixes": ["strict_"],
                        "needs_review_reason_prefixes": ["runtime_regression"],
                        "fail_on_needs_review_risk_levels": ["high"],
                        "fail_on_unknown_reasons": True,
                        "dry_run_human_checks": {
                            "base": ["custom-base"],
                            "medium_extra": ["custom-medium"],
                            "high_extra": ["custom-high"],
                            "changeset_extra": ["custom-cs"],
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "apply deterministic patch and run",
                    "--context-json",
                    str(context),
                    "--policy",
                    str(policy),
                    "--materialize-change-set",
                    "--dry-run",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            checks = payload.get("planned_required_human_checks", [])
            self.assertEqual(checks, ["custom-base", "custom-medium", "custom-high", "custom-cs"])

    def test_autopilot_materializes_change_set_from_planner(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            out = root / "summary.json"
            intent_out = root / "intent.json"
            self._write_baseline(baseline)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "apply deterministic patch and run",
                    "--planner-backend",
                    "rule",
                    "--materialize-change-set",
                    "--proposal-id",
                    "autopilot-change-set-1",
                    "--baseline",
                    str(baseline),
                    "--intent-out",
                    str(intent_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "PASS")
            self.assertTrue(payload["materialize_change_set"])
            self.assertTrue(payload["generated_change_set_path"])
            self.assertEqual(payload["generated_change_set_source"], "change_plan")
            self.assertEqual(payload["change_apply_status"], "applied")
            self.assertTrue(payload["change_set_hash"])
            self.assertEqual(payload["applied_changes_count"], 1)
            self.assertEqual(payload["change_plan_confidence_min"], 0.9)
            generated_path = Path(payload["generated_change_set_path"])
            self.assertTrue(generated_path.exists())
            intent_payload = json.loads(intent_out.read_text(encoding="utf-8"))
            self.assertIn("change_set_path", intent_payload.get("overrides", {}))
            self.assertIn("change_plan_guardrails", intent_payload.get("planner_inputs", {}))

    def test_autopilot_materialize_respects_planner_confidence_guardrail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            out = root / "summary.json"
            context = root / "context.json"
            self._write_baseline(baseline)
            context.write_text(json.dumps({"change_plan_confidence": 0.4}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "apply deterministic patch and run",
                    "--planner-backend",
                    "rule",
                    "--materialize-change-set",
                    "--context-json",
                    str(context),
                    "--planner-change-plan-confidence-min",
                    "0.8",
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
            self.assertEqual(payload["planner_exit_code"], 1)
            self.assertEqual(payload["status"], "UNKNOWN")
            self.assertIn("planner_stderr_tail", payload)

    def test_autopilot_emits_checker_template(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            out = root / "summary.json"
            self._write_baseline(baseline)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "run demo mock pass",
                    "--proposal-id",
                    "autopilot-checker-template-1",
                    "--baseline",
                    str(baseline),
                    "--emit-checker-template",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(payload["emit_checker_template"])
            self.assertEqual(
                payload["planned_run"]["checker_template_out"],
                "artifacts/autopilot/checker_template.json",
            )
            self.assertEqual(payload["checker_template_path"], "artifacts/autopilot/checker_template.json")
            self.assertTrue(Path("artifacts/autopilot/checker_template.json").exists())

    def test_autopilot_dry_run_accepts_policy_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "run demo mock pass",
                    "--dry-run",
                    "--policy-profile",
                    "industrial_strict_v0",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "PLANNED")
            self.assertTrue(str(payload["planned_run"]["policy"]).endswith("industrial_strict_v0.json"))


if __name__ == "__main__":
    unittest.main()
