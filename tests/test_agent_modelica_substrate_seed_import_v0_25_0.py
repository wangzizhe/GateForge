from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_substrate_seed_import_v0_25_0 import (
    build_substrate_seed_import,
    classify_import_status,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class SubstrateSeedImportV0250Tests(unittest.TestCase):
    def test_classify_import_status_uses_repeatability_gate(self) -> None:
        self.assertEqual(
            classify_import_status(
                {"registry_policy": "benchmark_positive_candidate"},
                {"repeatability_class": "stable_true_multi"},
            ),
            "promoted_family_prototype",
        )
        self.assertEqual(
            classify_import_status(
                {"registry_policy": "hard_negative_candidate"},
                {"repeatability_class": "stable_dead_end"},
            ),
            "hard_negative",
        )

    def test_build_substrate_seed_import_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seeds = root / "seeds.jsonl"
            repeatability = root / "repeatability.jsonl"
            out_dir = root / "out"
            _write_jsonl(
                seeds,
                [
                    {
                        "seed_id": "case1",
                        "candidate_id": "case1",
                        "registry_policy": "benchmark_positive_candidate",
                        "artifact_references": ["artifact.json"],
                    }
                ],
            )
            _write_jsonl(repeatability, [{"candidate_id": "case1", "repeatability_class": "stable_true_multi"}])

            summary = build_substrate_seed_import(
                seed_registry_path=seeds,
                candidate_repeatability_path=repeatability,
                out_dir=out_dir,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["import_status_counts"]["promoted_family_prototype"], 1)
            self.assertTrue((out_dir / "substrate_seed_import.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
