from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_substrate_split_v0_25_2 import assign_split, build_substrate_split


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class SubstrateSplitV0252Tests(unittest.TestCase):
    def test_assign_split_preserves_hard_negative(self) -> None:
        split = assign_split(
            {"seed_id": "s", "import_status": "hard_negative"},
            admitted_ids={"s"},
            holdout_ids=set(),
        )
        self.assertEqual(split, "hard_negative")

    def test_build_substrate_split_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            imported = root / "imported.jsonl"
            admission = root / "admission.jsonl"
            smoke = root / "smoke.jsonl"
            out_dir = root / "out"
            _write_jsonl(
                imported,
                [
                    {"seed_id": "p", "import_status": "promoted_family_prototype", "mutation_family": "f", "artifact_references": ["a"]},
                    {"seed_id": "n", "import_status": "hard_negative", "mutation_family": "f", "artifact_references": ["a"]},
                ],
            )
            _write_jsonl(admission, [{"seed_id": "p", "admission_status": "admitted"}, {"seed_id": "n", "admission_status": "admitted"}])
            _write_jsonl(smoke, [{"seed_id": "smoke", "candidate_id": "smoke", "repeatability_class": "fixture"}])

            summary = build_substrate_split(import_path=imported, admission_path=admission, smoke_path=smoke, out_dir=out_dir)

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["split_counts"]["positive"], 1)
            self.assertEqual(summary["split_counts"]["hard_negative"], 1)
            self.assertEqual(summary["split_counts"]["smoke"], 1)


if __name__ == "__main__":
    unittest.main()
