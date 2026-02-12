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
        change_set_path: str | None = None,
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
            "risk_level": "low",
        }
        if change_set_path is not None:
            payload["change_set_path"] = change_set_path
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


if __name__ == "__main__":
    unittest.main()
