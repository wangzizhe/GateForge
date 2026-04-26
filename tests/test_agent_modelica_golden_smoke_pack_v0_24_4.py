from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_golden_smoke_pack_v0_24_4 import (
    build_golden_smoke_pack,
    build_smoke_seed_rows,
    build_smoke_trajectories,
)


class GoldenSmokePackV0244Tests(unittest.TestCase):
    def test_build_smoke_seed_rows_are_public_and_non_routing(self) -> None:
        rows = build_smoke_seed_rows()

        self.assertTrue(rows)
        self.assertTrue(all(row["public_status"] == "public_fixture" for row in rows))
        self.assertTrue(all(row["routing_allowed"] is False for row in rows))

    def test_build_smoke_trajectories_cover_success_failure_and_noise(self) -> None:
        rows = build_smoke_trajectories()
        verdicts = {row["final_verdict"] for row in rows}

        self.assertIn("PASS", verdicts)
        self.assertIn("FAILED", verdicts)
        self.assertIn("PROVIDER_ERROR", verdicts)
        self.assertIn("INFRA_ERROR", verdicts)

    def test_build_golden_smoke_pack_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"

            summary = build_golden_smoke_pack(out_dir=out_dir)

            self.assertEqual(summary["status"], "PASS")
            self.assertFalse(summary["private_asset_required"])
            self.assertEqual(summary["validation_error_count"], 0)
            self.assertTrue((out_dir / "seed_registry.jsonl").exists())
            self.assertTrue((out_dir / "normalized_trajectories.jsonl").exists())
            self.assertTrue((out_dir / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
