from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_substrate_manifest_v0_25_3 import (
    build_substrate_manifest,
    stable_hash,
    validate_manifest_rows,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class SubstrateManifestV0253Tests(unittest.TestCase):
    def test_stable_hash_is_order_independent(self) -> None:
        self.assertEqual(stable_hash({"a": 1, "b": 2}), stable_hash({"b": 2, "a": 1}))

    def test_validate_manifest_rows_rejects_duplicates(self) -> None:
        errors = validate_manifest_rows(
            [
                {"seed_id": "s", "artifact_hash": "h", "artifact_references": ["a"], "routing_allowed": False},
                {"seed_id": "s", "artifact_hash": "h", "artifact_references": ["a"], "routing_allowed": False},
            ]
        )
        self.assertTrue(any("duplicate_seed_id" in row["errors"] for row in errors))

    def test_build_substrate_manifest_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split = root / "split.jsonl"
            out_dir = root / "out"
            _write_jsonl(split, [{"seed_id": "s", "split": "positive", "artifact_references": ["a"]}])
            summary = build_substrate_manifest(split_path=split, out_dir=out_dir)
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "manifest.json").exists())
            self.assertTrue((out_dir / "manifest_rows.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
