import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaV01957TrajectoryStoreTests(unittest.TestCase):
    def test_build_script_writes_store_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            input_dir = root / "input"
            out_dir = root / "out"
            input_dir.mkdir()
            (input_dir / "case.json").write_text(
                json.dumps(
                    {
                        "candidate_id": "v01945_Example_v0_pp_a_pv_b",
                        "mode": "multi-c5",
                        "final_status": "pass",
                        "round_count": 1,
                        "rounds": [
                            {
                                "round": 1,
                                "omc_output": "The model is underdetermined with too few equations.",
                                "advance": "pass",
                                "ranked": [{"check_pass": True, "simulate_pass": True, "deficit": 2}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "scripts/build_trajectory_store_v0_19_57.py",
                    "--input-dir",
                    str(input_dir),
                    "--out-dir",
                    str(out_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            store = json.loads((out_dir / "store.json").read_text(encoding="utf-8"))
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(store["entry_count"], 1)
            self.assertEqual(summary["entry_count"], 1)
            self.assertTrue(summary["latency_pass"])
            self.assertEqual(summary["sample_retrieval"]["hits"][0]["mutation_family"], "compound_underdetermined")


if __name__ == "__main__":
    unittest.main()

