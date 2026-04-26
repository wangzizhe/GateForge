from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_substrate_admission_v0_25_1 import build_substrate_admission, evaluate_admission


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class SubstrateAdmissionV0251Tests(unittest.TestCase):
    def test_evaluate_admission_blocks_routing_dependency(self) -> None:
        row = evaluate_admission(
            {
                "seed_id": "s",
                "source_model": "m",
                "artifact_references": ["a"],
                "omc_admission_status": "admitted",
                "repeatability_class": "stable_true_multi",
                "import_status": "promoted_family_prototype",
                "routing_allowed": True,
            }
        )
        self.assertEqual(row["admission_status"], "research_pool")
        self.assertIn("routing_or_hint_dependency", row["blocking_reasons"])

    def test_build_substrate_admission_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            imported = root / "imported.jsonl"
            out_dir = root / "out"
            _write_jsonl(
                imported,
                [
                    {
                        "seed_id": "s",
                        "source_model": "m",
                        "artifact_references": ["a"],
                        "omc_admission_status": "admitted_via_source_artifact",
                        "repeatability_class": "stable_true_multi",
                        "import_status": "promoted_family_prototype",
                        "routing_allowed": False,
                    }
                ],
            )
            summary = build_substrate_admission(imported_seeds_path=imported, out_dir=out_dir)
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["admission_status_counts"]["admitted"], 1)
            self.assertTrue((out_dir / "substrate_admission.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
