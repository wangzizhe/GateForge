import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaRepairMemoryBackfillV1Tests(unittest.TestCase):
    def test_backfill_populates_signature_reason_and_split(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_backfill_") as td:
            root = Path(td)
            memory = root / "memory.json"
            out = root / "summary.json"
            memory.write_text(
                json.dumps(
                    {
                        "schema_version": "agent_modelica_repair_memory_v1",
                        "rows": [
                            {
                                "fingerprint": "fp1",
                                "task_id": "t1",
                                "failure_type": "simulate_error",
                                "scale": "small",
                                "used_strategy": "s1",
                                "action_trace": ["a1"],
                                "success": True,
                            },
                            {
                                "fingerprint": "fp2",
                                "task_id": "t2",
                                "failure_type": "simulate_error",
                                "scale": "small",
                                "used_strategy": "s1",
                                "action_trace": ["a1"],
                                "success": False,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_repair_memory_backfill_v1",
                    "--memory",
                    str(memory),
                    "--holdout-ratio",
                    "0.5",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            updated = json.loads(memory.read_text(encoding="utf-8"))
            rows = updated.get("rows", [])
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(str(r.get("error_signature") or "").strip() for r in rows))
            self.assertTrue(all(str(r.get("gate_break_reason") or "").strip() for r in rows))
            self.assertTrue(all(str(r.get("split") or "").strip() in {"train", "holdout"} for r in rows))
            self.assertGreaterEqual(
                sum(1 for r in rows if str(r.get("split") or "").strip() == "holdout"),
                1,
            )


if __name__ == "__main__":
    unittest.main()
