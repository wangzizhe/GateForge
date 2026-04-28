from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_dyad_methodology_closeout_v0_29_25 import build_dyad_methodology_closeout


class DyadMethodologyCloseoutV02925Tests(unittest.TestCase):
    def test_build_closeout_summary_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            summary = build_dyad_methodology_closeout(out_dir=out_dir)
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["next_stage"]["recommended"], "transparent_verifier_or_candidate_critique")
            classifications = {row["method"]: row["classification"] for row in summary["method_classifications"]}
            self.assertEqual(classifications["tool_use_harness"], "promote_as_default_architecture")
            self.assertEqual(classifications["oracle_boundary_prompt"], "negative_result")
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
