import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RunTests(unittest.TestCase):
    def _write_proposal(
        self,
        path: Path,
        actions: list[str],
        *,
        backend: str = "mock",
        risk_level: str = "low",
        change_set_path: str | None = None,
        checkers: list[str] | None = None,
    ) -> None:
        payload = {
            "schema_version": "0.1.0",
            "proposal_id": "proposal-run-1",
            "timestamp_utc": "2026-02-11T10:00:00Z",
            "author_type": "human",
            "backend": backend,
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "change_summary": "proposal-driven run",
            "requested_actions": actions,
            "risk_level": risk_level,
        }
        if change_set_path is not None:
            payload["change_set_path"] = change_set_path
        if checkers is not None:
            payload["checkers"] = checkers
        path.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    def _write_baseline(self, path: Path, backend: str = "mock") -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": "base-1",
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

    def _write_candidate(
        self,
        path: Path,
        *,
        failure_type: str,
        gate: str = "FAIL",
        runtime: float = 0.1,
        status: str = "failed",
        check_ok: bool = False,
        simulate_ok: bool = False,
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": "cand-1",
                    "backend": "mock",
                    "model_script": "examples/openmodelica/minimal_probe.mos",
                    "status": status,
                    "failure_type": failure_type,
                    "gate": gate,
                    "check_ok": check_ok,
                    "simulate_ok": simulate_ok,
                    "metrics": {"runtime_seconds": runtime},
                    "artifacts": {"log_excerpt": "permission denied while trying to connect to the Docker daemon socket"},
                }
            ),
            encoding="utf-8",
        )

    def test_run_proposal_check_simulate_regress_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            out = root / "run_summary.json"
            candidate = root / "candidate.json"
            regression = root / "regression.json"

            self._write_proposal(proposal, ["check", "simulate", "regress"])
            self._write_baseline(baseline)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--baseline",
                    str(baseline),
                    "--candidate-out",
                    str(candidate),
                    "--regression-out",
                    str(regression),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["smoke_executed"])
            self.assertTrue(summary["regress_executed"])
            candidate_payload = json.loads(candidate.read_text(encoding="utf-8"))
            self.assertEqual(candidate_payload["proposal_id"], "proposal-run-1")
            regression_payload = json.loads(regression.read_text(encoding="utf-8"))
            self.assertEqual(regression_payload["proposal_id"], "proposal-run-1")

    def test_run_proposal_regress_fails_on_baseline_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            out = root / "run_summary.json"

            self._write_proposal(proposal, ["check", "simulate", "regress"])
            self._write_baseline(baseline, backend="openmodelica_docker")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
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
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "FAIL")
            self.assertIn("regression_fail", summary["fail_reasons"])

    def test_run_proposal_auto_baseline_uses_index(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            index = root / "index.json"
            out = root / "run_summary.json"

            self._write_proposal(proposal, ["check", "simulate", "regress"])
            self._write_baseline(baseline, backend="mock")
            index.write_text(
                json.dumps(
                    {
                        "version": "0.1.0",
                        "entries": [
                            {
                                "backend": "mock",
                                "model_script": "examples/openmodelica/minimal_probe.mos",
                                "baseline": str(baseline),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--baseline",
                    "auto",
                    "--baseline-index",
                    str(index),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["baseline_path"], str(baseline))

    def test_run_proposal_auto_baseline_missing_mapping_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            index = root / "index.json"
            out = root / "run_summary.json"

            self._write_proposal(proposal, ["check", "simulate", "regress"])
            index.write_text(
                json.dumps({"version": "0.1.0", "entries": []}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--baseline",
                    "auto",
                    "--baseline-index",
                    str(index),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("No baseline mapping found", proc.stderr + proc.stdout)

    def test_run_proposal_includes_docker_error_hints(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            out = root / "run_summary.json"
            report = root / "run_summary.md"

            self._write_proposal(proposal, ["regress"])
            self._write_baseline(baseline, backend="mock")
            self._write_candidate(candidate, failure_type="docker_error")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--candidate-in",
                    str(candidate),
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(out),
                    "--report",
                    str(report),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(summary["human_hints"])
            self.assertIn("Docker backend execution failed", summary["human_hints"][0])
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("## Human Hints", report_text)
            self.assertIn("Docker backend execution failed", report_text)

    def test_run_proposal_needs_review_includes_required_checks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            out = root / "run_summary.json"
            report = root / "run_summary.md"

            self._write_proposal(proposal, ["regress"])
            self._write_baseline(baseline, backend="mock")
            baseline_payload = json.loads(baseline.read_text(encoding="utf-8"))
            baseline_payload["metrics"]["runtime_seconds"] = 0.5
            baseline.write_text(json.dumps(baseline_payload), encoding="utf-8")
            self._write_candidate(
                candidate,
                failure_type="none",
                gate="PASS",
                runtime=1.0,
                status="success",
                check_ok=True,
                simulate_ok=True,
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--candidate-in",
                    str(candidate),
                    "--baseline",
                    str(baseline),
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
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "NEEDS_REVIEW")
            self.assertTrue(summary["required_human_checks"])
            self.assertIn("runtime", summary["required_human_checks"][0].lower())
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("## Required Human Checks", report_text)

    def test_run_proposal_applies_change_set_successfully(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            out = root / "run_summary.json"
            report = root / "run_summary.md"

            self._write_proposal(
                proposal,
                ["check", "simulate", "regress"],
                change_set_path="examples/changesets/minimalprobe_x_to_2.json",
            )
            self._write_baseline(baseline)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--baseline",
                    str(baseline),
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
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["change_apply_status"], "applied")
            self.assertTrue(summary["change_set_hash"])
            self.assertTrue(summary["applied_changes"])
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("## Applied Changes", report_text)

    def test_run_proposal_fails_when_change_set_apply_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            out = root / "run_summary.json"

            self._write_proposal(
                proposal,
                ["check", "simulate"],
                change_set_path="examples/changesets/minimalprobe_bad_old_text.json",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
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
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "FAIL")
            self.assertEqual(summary["change_apply_status"], "failed")
            self.assertIn("change_apply_failed", summary["fail_reasons"])
            self.assertTrue(summary["required_human_checks"])
            joined = " ".join(summary["required_human_checks"]).lower()
            self.assertIn("change_set", joined)

    def test_run_proposal_high_risk_change_set_requires_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            out = root / "run_summary.json"

            self._write_proposal(
                proposal,
                ["check", "simulate"],
                risk_level="high",
                change_set_path="examples/changesets/minimalprobe_x_to_2.json",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
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
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "NEEDS_REVIEW")
            self.assertEqual(summary["change_apply_status"], "requires_review")
            self.assertFalse(summary["smoke_executed"])
            self.assertIn("change_requires_human_review", summary["policy_reasons"])

    def test_run_proposal_change_set_preflight_failed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            out = root / "run_summary.json"
            bad_changeset = root / "bad_change_set.json"
            bad_changeset.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "changes": [
                            {
                                "op": "replace_text",
                                "file": "examples/not_allowed/Bad.mo",
                                "old": "x",
                                "new": "y",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            self._write_proposal(
                proposal,
                ["check", "simulate"],
                change_set_path=str(bad_changeset),
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
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
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "FAIL")
            self.assertEqual(summary["change_apply_status"], "preflight_failed")
            self.assertEqual(summary["change_preflight_status"], "failed")
            self.assertIn("change_preflight_failed", summary["fail_reasons"])

    def test_run_proposal_change_set_low_confidence_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            out = root / "run_summary.json"
            conf_changeset = root / "confidence_change_set.json"
            conf_changeset.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "changes": [
                            {
                                "op": "replace_text",
                                "file": "examples/openmodelica/MinimalProbe.mo",
                                "old": "der(x) = -x;",
                                "new": "der(x) = -2*x;",
                            }
                        ],
                        "metadata": {
                            "plan_confidence_min": 0.5,
                            "plan_confidence_avg": 0.5,
                            "plan_confidence_max": 0.5,
                        },
                    }
                ),
                encoding="utf-8",
            )
            self._write_proposal(
                proposal,
                ["check", "simulate"],
                risk_level="low",
                change_set_path=str(conf_changeset),
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
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
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "NEEDS_REVIEW")
            self.assertEqual(summary["change_apply_status"], "requires_review")
            self.assertEqual(summary["change_plan_confidence_min"], 0.5)
            self.assertIn("change_plan_confidence_below_auto_apply", summary["policy_reasons"])

    def test_run_proposal_change_set_very_low_confidence_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            out = root / "run_summary.json"
            conf_changeset = root / "confidence_change_set_fail.json"
            conf_changeset.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "changes": [
                            {
                                "op": "replace_text",
                                "file": "examples/openmodelica/MinimalProbe.mo",
                                "old": "der(x) = -x;",
                                "new": "der(x) = -2*x;",
                            }
                        ],
                        "metadata": {
                            "plan_confidence_min": 0.2,
                            "plan_confidence_avg": 0.2,
                            "plan_confidence_max": 0.2,
                        },
                    }
                ),
                encoding="utf-8",
            )
            self._write_proposal(
                proposal,
                ["check", "simulate"],
                risk_level="low",
                change_set_path=str(conf_changeset),
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
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
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "FAIL")
            self.assertEqual(summary["change_apply_status"], "rejected_low_confidence")
            self.assertIn("change_plan_confidence_below_accept", summary["policy_reasons"])

    def test_run_proposal_uses_configured_checkers(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            out = root / "run_summary.json"
            regression = root / "regression.json"

            self._write_proposal(
                proposal,
                ["regress"],
                checkers=["nan_inf"],
            )
            self._write_baseline(baseline, backend="mock")
            self._write_candidate(
                candidate,
                failure_type="none",
                gate="PASS",
                status="success",
                check_ok=True,
                simulate_ok=True,
            )
            candidate_payload = json.loads(candidate.read_text(encoding="utf-8"))
            candidate_payload["artifacts"]["log_excerpt"] = "solver produced NaN at t=0.1"
            candidate.write_text(json.dumps(candidate_payload), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--candidate-in",
                    str(candidate),
                    "--baseline",
                    str(baseline),
                    "--regression-out",
                    str(regression),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "FAIL")
            self.assertIn("regression_fail", summary["fail_reasons"])
            self.assertEqual(summary["checkers"], ["nan_inf"])
            self.assertEqual(summary["checker_config"], {})
            regression_payload = json.loads(regression.read_text(encoding="utf-8"))
            self.assertIn("nan_inf_detected", regression_payload["reasons"])
            self.assertEqual(regression_payload["checkers"], ["nan_inf"])

    def test_run_proposal_uses_checker_config(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            out = root / "run_summary.json"
            regression = root / "regression.json"

            self._write_proposal(
                proposal,
                ["regress"],
                checkers=["performance_regression"],
            )
            proposal_payload = json.loads(proposal.read_text(encoding="utf-8"))
            proposal_payload["checker_config"] = {"performance_regression": {"max_ratio": 1.5}}
            proposal.write_text(json.dumps(proposal_payload), encoding="utf-8")

            self._write_baseline(baseline, backend="mock")
            self._write_candidate(
                candidate,
                failure_type="none",
                gate="PASS",
                status="success",
                check_ok=True,
                simulate_ok=True,
                runtime=1.6,
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--candidate-in",
                    str(candidate),
                    "--baseline",
                    str(baseline),
                    "--runtime-threshold",
                    "10",
                    "--regression-out",
                    str(regression),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "NEEDS_REVIEW")
            self.assertEqual(summary["checkers"], ["performance_regression"])
            self.assertEqual(summary["checker_config"]["performance_regression"]["max_ratio"], 1.5)
            regression_payload = json.loads(regression.read_text(encoding="utf-8"))
            self.assertIn("performance_regression_detected", regression_payload["reasons"])
            self.assertEqual(regression_payload["checker_config"]["performance_regression"]["max_ratio"], 1.5)

    def test_run_emits_checker_template_for_selected_checkers(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            out = root / "run_summary.json"
            template_out = root / "checker_template.json"

            self._write_proposal(
                proposal,
                ["regress"],
                checkers=["performance_regression", "control_behavior_regression"],
            )
            self._write_baseline(baseline, backend="mock")
            self._write_candidate(
                candidate,
                failure_type="none",
                gate="PASS",
                status="success",
                check_ok=True,
                simulate_ok=True,
                runtime=1.0,
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--candidate-in",
                    str(candidate),
                    "--baseline",
                    str(baseline),
                    "--emit-checker-template",
                    str(template_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            self.assertTrue(template_out.exists())
            template_payload = json.loads(template_out.read_text(encoding="utf-8"))
            self.assertIn("performance_regression", template_payload)
            self.assertIn("control_behavior_regression", template_payload)
            self.assertIn("_runtime", template_payload)
            self.assertNotIn("event_explosion", template_payload)
            self.assertEqual(template_payload["performance_regression"]["max_ratio"], 2.0)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["checker_template_path"], str(template_out))

    def test_run_emits_checker_template_for_all_when_checkers_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            out = root / "run_summary.json"
            template_out = root / "checker_template_all.json"

            self._write_proposal(proposal, ["regress"])
            self._write_baseline(baseline, backend="mock")
            self._write_candidate(
                candidate,
                failure_type="none",
                gate="PASS",
                status="success",
                check_ok=True,
                simulate_ok=True,
                runtime=1.0,
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--candidate-in",
                    str(candidate),
                    "--baseline",
                    str(baseline),
                    "--emit-checker-template",
                    str(template_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            template_payload = json.loads(template_out.read_text(encoding="utf-8"))
            self.assertIn("performance_regression", template_payload)
            self.assertIn("event_explosion", template_payload)
            self.assertIn("steady_state_regression", template_payload)
            self.assertIn("control_behavior_regression", template_payload)

    def test_run_proposal_fails_on_unknown_policy_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            out = root / "run_summary.json"

            self._write_proposal(proposal, ["regress"])
            self._write_baseline(baseline, backend="mock")
            self._write_candidate(
                candidate,
                failure_type="none",
                gate="PASS",
                status="success",
                check_ok=True,
                simulate_ok=True,
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--candidate-in",
                    str(candidate),
                    "--baseline",
                    str(baseline),
                    "--policy-profile",
                    "does_not_exist_profile",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
