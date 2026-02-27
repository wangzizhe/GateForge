import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelIntakePipelineV1Tests(unittest.TestCase):
    def test_intake_pipeline_accepts_valid_real_models(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_path = root / "model_a.mo"
            model_path.write_text("model A\nequation\nend A;\n", encoding="utf-8")
            catalog = root / "catalog.json"
            out = root / "summary.json"
            rows_out = root / "rows.json"
            ledger_out = root / "ledger.json"

            catalog.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "model_id": "mdl_a",
                                "name": "ModelA",
                                "local_path": str(model_path),
                                "source_url": "https://example.com/repo/model_a.mo",
                                "license": "MIT",
                                "scale_hint": "medium",
                                "complexity_score": 120,
                                "repro_command": "python -c \"print('ok')\"",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_intake_pipeline_v1",
                    "--candidate-catalog",
                    str(catalog),
                    "--registry-rows-out",
                    str(rows_out),
                    "--ledger-out",
                    str(ledger_out),
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
            self.assertEqual(int(summary.get("accepted_count", 0)), 1)

    def test_intake_pipeline_needs_review_when_probe_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_path = root / "model_b.mo"
            model_path.write_text("model B\nequation\nend B;\n", encoding="utf-8")
            catalog = root / "catalog.json"
            out = root / "summary.json"

            catalog.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "model_id": "mdl_b",
                                "name": "ModelB",
                                "local_path": str(model_path),
                                "source_url": "https://example.com/repo/model_b.mo",
                                "license": "MIT",
                                "scale_hint": "medium",
                                "complexity_score": 120,
                                "repro_command": "unknown_command --arg",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_intake_pipeline_v1",
                    "--candidate-catalog",
                    str(catalog),
                    "--probe-mode",
                    "syntax",
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
            self.assertGreaterEqual(int(summary.get("probe_fail_count", 0)), 1)

    def test_intake_pipeline_fail_when_catalog_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_intake_pipeline_v1",
                    "--candidate-catalog",
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
