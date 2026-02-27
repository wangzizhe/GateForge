import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelIntakeRunnerV1Tests(unittest.TestCase):
    def test_runner_pass_with_weekly_targets_met(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "small.mo").write_text("model A\n  Real x;\nequation\n  der(x) = -x;\nend A;\n", encoding="utf-8")
            (root / "medium.mo").write_text("model B\n  Real x;\nequation\n  der(x) = -x;\nend B;\n", encoding="utf-8")
            (root / "large.mo").write_text("model C\n  Real x;\nequation\n  der(x) = -x;\nend C;\n", encoding="utf-8")
            queue = root / "queue.jsonl"
            queue.write_text(
                "\n".join(
                    [
                        json.dumps({"source_url": "https://x/small.mo", "license": "MIT", "domain": "pressure", "expected_scale": "small", "model_path": str(root / "small.mo"), "version_hint": "v1"}),
                        json.dumps({"source_url": "https://x/medium.mo", "license": "MIT", "domain": "pressure", "expected_scale": "medium", "model_path": str(root / "medium.mo"), "version_hint": "v1"}),
                        json.dumps({"source_url": "https://x/large.mo", "license": "MIT", "domain": "pressure", "expected_scale": "large", "model_path": str(root / "large.mo"), "version_hint": "v1"}),
                    ]
                ),
                encoding="utf-8",
            )
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_intake_runner_v1",
                    "--intake-queue-jsonl",
                    str(queue),
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
            self.assertEqual(int(summary.get("accepted_count", 0)), 3)
            self.assertEqual(summary.get("weekly_target_status"), "PASS")

    def test_runner_needs_review_when_large_target_missed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "small.mo").write_text("model A\n  Real x;\nequation\n  der(x) = -x;\nend A;\n", encoding="utf-8")
            queue = root / "queue.jsonl"
            queue.write_text(
                "\n".join(
                    [
                        json.dumps({"source_url": "https://x/s1.mo", "license": "MIT", "domain": "pressure", "expected_scale": "small", "model_path": str(root / "small.mo"), "version_hint": "v1"}),
                        json.dumps({"source_url": "https://x/s2.mo", "license": "MIT", "domain": "pressure", "expected_scale": "small", "model_path": str(root / "small.mo"), "version_hint": "v1"}),
                        json.dumps({"source_url": "https://x/s3.mo", "license": "MIT", "domain": "pressure", "expected_scale": "small", "model_path": str(root / "small.mo"), "version_hint": "v1"}),
                    ]
                ),
                encoding="utf-8",
            )
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_intake_runner_v1",
                    "--intake-queue-jsonl",
                    str(queue),
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
            self.assertIn("weekly_large_accepted_below_target", summary.get("target_gaps", []))

    def test_runner_fail_when_queue_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_intake_runner_v1",
                    "--intake-queue-jsonl",
                    str(root / "missing.jsonl"),
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
