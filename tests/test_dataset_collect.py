import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.dataset_collect import collect_summaries


class DatasetCollectTests(unittest.TestCase):
    def test_collect_summaries_classifies_known_types(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "bench").mkdir(parents=True, exist_ok=True)
            (root / "mutation").mkdir(parents=True, exist_ok=True)
            (root / "run").mkdir(parents=True, exist_ok=True)
            (root / "autopilot").mkdir(parents=True, exist_ok=True)

            (root / "bench" / "summary.json").write_text(
                json.dumps(
                    {
                        "pack_id": "pack_v0",
                        "total_cases": 1,
                        "pass_count": 1,
                        "fail_count": 0,
                        "cases": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "mutation" / "summary.json").write_text(
                json.dumps(
                    {
                        "pack_id": "mutation_pack_v1",
                        "total_cases": 1,
                        "pass_count": 1,
                        "fail_count": 0,
                        "cases": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "run" / "run_summary.json").write_text(
                json.dumps({"proposal_id": "p1", "smoke_executed": True}),
                encoding="utf-8",
            )
            (root / "autopilot" / "summary.json").write_text(
                json.dumps(
                    {
                        "intent_path": "a.json",
                        "planner_exit_code": 0,
                        "agent_run_exit_code": 0,
                    }
                ),
                encoding="utf-8",
            )

            payload = collect_summaries(str(root))
            counts = payload.get("counts", {})
            self.assertEqual(counts.get("benchmark_summary_count"), 1)
            self.assertEqual(counts.get("mutation_summary_count"), 1)
            self.assertEqual(counts.get("run_summary_count"), 1)
            self.assertEqual(counts.get("autopilot_summary_count"), 1)

    def test_collect_cli_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "collect_summary.json"
            (root / "bench.json").write_text(
                json.dumps(
                    {
                        "pack_id": "pack_v0",
                        "total_cases": 1,
                        "pass_count": 1,
                        "fail_count": 0,
                        "cases": [],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_collect",
                    "--root",
                    str(root),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("counts", {}).get("benchmark_summary_count"), 1)


if __name__ == "__main__":
    unittest.main()
