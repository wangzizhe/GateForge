import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelicaLibraryExpansionPlanV1Tests(unittest.TestCase):
    def test_expansion_plan_needs_review_when_debt_open(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            intake = root / "intake.json"
            registry = root / "registry.json"
            saturation = root / "saturation.json"
            push = root / "push.json"
            out = root / "summary.json"

            intake.write_text(json.dumps({"accepted_count": 2, "rejected_count": 4}), encoding="utf-8")
            registry.write_text(
                json.dumps({"total_assets": 8, "scale_counts": {"small": 4, "medium": 3, "large": 1}}),
                encoding="utf-8",
            )
            saturation.write_text(json.dumps({"saturation_index": 62.0, "total_gap_actions": 6}), encoding="utf-8")
            push.write_text(json.dumps({"push_target_large_cases": 5}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_library_expansion_plan_v1",
                    "--open-source-intake-summary",
                    str(intake),
                    "--modelica-library-registry-summary",
                    str(registry),
                    "--failure-corpus-saturation-summary",
                    str(saturation),
                    "--large-coverage-push-v1-summary",
                    str(push),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
            self.assertIn("large_coverage_debt_open", summary.get("alerts", []))

    def test_expansion_plan_pass_with_good_signals(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            intake = root / "intake.json"
            registry = root / "registry.json"
            saturation = root / "saturation.json"
            push = root / "push.json"
            out = root / "summary.json"

            intake.write_text(json.dumps({"accepted_count": 8, "rejected_count": 1}), encoding="utf-8")
            registry.write_text(
                json.dumps({"total_assets": 40, "scale_counts": {"small": 12, "medium": 14, "large": 14}}),
                encoding="utf-8",
            )
            saturation.write_text(json.dumps({"saturation_index": 90.0, "total_gap_actions": 0}), encoding="utf-8")
            push.write_text(json.dumps({"push_target_large_cases": 0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_library_expansion_plan_v1",
                    "--open-source-intake-summary",
                    str(intake),
                    "--modelica-library-registry-summary",
                    str(registry),
                    "--failure-corpus-saturation-summary",
                    str(saturation),
                    "--large-coverage-push-v1-summary",
                    str(push),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(float(summary.get("expansion_readiness_score", 0.0)), 72.0)

    def test_expansion_plan_fail_when_required_input_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_library_expansion_plan_v1",
                    "--open-source-intake-summary",
                    str(root / "missing_intake.json"),
                    "--modelica-library-registry-summary",
                    str(root / "missing_registry.json"),
                    "--failure-corpus-saturation-summary",
                    str(root / "missing_saturation.json"),
                    "--large-coverage-push-v1-summary",
                    str(root / "missing_push.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
