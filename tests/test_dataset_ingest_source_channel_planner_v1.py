import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetIngestSourceChannelPlannerV1Tests(unittest.TestCase):
    def test_planner_builds_channels(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            discovery = root / "discovery.json"
            runner = root / "runner.json"
            canonical = root / "canonical.json"
            backfill = root / "backfill.json"
            out = root / "summary.json"
            plan = root / "channels.json"

            discovery.write_text(json.dumps({"total_candidates": 30}), encoding="utf-8")
            runner.write_text(json.dumps({"accepted_count": 10, "accepted_large_count": 2, "rejected_count": 3}), encoding="utf-8")
            canonical.write_text(json.dumps({"canonical_new_models": 8, "canonical_net_growth_models": 5}), encoding="utf-8")
            backfill.write_text(json.dumps({"total_tasks": 4, "p0_tasks": 1}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_ingest_source_channel_planner_v1",
                    "--asset-discovery-summary",
                    str(discovery),
                    "--intake-runner-summary",
                    str(runner),
                    "--canonical-registry-summary",
                    str(canonical),
                    "--coverage-backfill-summary",
                    str(backfill),
                    "--plan-out",
                    str(plan),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertGreaterEqual(int(payload.get("total_channels", 0)), 3)
            self.assertTrue(plan.exists())

    def test_planner_fail_when_required_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_ingest_source_channel_planner_v1",
                    "--asset-discovery-summary",
                    str(root / "missing_discovery.json"),
                    "--intake-runner-summary",
                    str(root / "missing_runner.json"),
                    "--canonical-registry-summary",
                    str(root / "missing_canonical.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
