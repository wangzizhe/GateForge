import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetReplayObservationStoreV1Tests(unittest.TestCase):
    def test_store_ingests_and_dedupes_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            raw = root / "raw.json"
            store = root / "store.jsonl"
            out = root / "summary.json"

            raw.write_text(
                json.dumps(
                    {
                        "schema_version": "mutation_raw_observations_v1",
                        "observations": [
                            {
                                "mutation_id": "m1",
                                "target_model_id": "mdl_x",
                                "target_scale": "large",
                                "execution_status": "EXECUTED",
                                "attempt_count": 1,
                                "repro_command": "cmd1",
                                "attempts": [
                                    {
                                        "return_code": 0,
                                        "timed_out": False,
                                        "exception": "",
                                        "duration_sec": 0.1,
                                        "stdout": "ok",
                                        "stderr": "",
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc1 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_replay_observation_store_v1",
                    "--raw-observations",
                    str(raw),
                    "--store-path",
                    str(store),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc1.returncode, 0, msg=proc1.stderr or proc1.stdout)
            s1 = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(int(s1.get("ingested_records", 0)), 1)

            proc2 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_replay_observation_store_v1",
                    "--raw-observations",
                    str(raw),
                    "--store-path",
                    str(store),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc2.returncode, 0, msg=proc2.stderr or proc2.stdout)
            s2 = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(int(s2.get("ingested_records", 0)), 0)
            self.assertGreaterEqual(int(s2.get("duplicate_records_skipped", 0)), 1)

    def test_store_fails_when_raw_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_replay_observation_store_v1",
                    "--raw-observations",
                    str(root / "missing.json"),
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
