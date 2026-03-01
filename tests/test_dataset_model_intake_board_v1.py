import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelIntakeBoardV1Tests(unittest.TestCase):
    def test_board_outputs_counts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            catalog = root / "catalog.json"
            intake = root / "intake.json"
            ledger = root / "ledger.json"
            out = root / "summary.json"
            catalog.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "model_id": "a",
                                "license": "MIT",
                                "scale_hint": "medium",
                                "complexity_score": 120,
                                "source_url": "https://example.com/a.mo",
                                "repro_command": "python -c \"print('ok')\"",
                            },
                            {
                                "model_id": "b",
                                "license": "UNKNOWN",
                                "scale_hint": "large",
                                "complexity_score": 110,
                                "source_url": "https://example.com/b.mo",
                                "repro_command": "",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            intake.write_text(json.dumps({"status": "PASS", "accepted_count": 1}), encoding="utf-8")
            ledger.write_text(json.dumps({"records": [{"model_id": "a", "decision": "ACCEPT"}]}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_intake_board_v1",
                    "--candidate-catalog",
                    str(catalog),
                    "--intake-summary",
                    str(intake),
                    "--intake-ledger",
                    str(ledger),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("total_candidates"), 2)
            self.assertGreaterEqual(payload.get("ingested_count", 0), 1)


if __name__ == "__main__":
    unittest.main()
