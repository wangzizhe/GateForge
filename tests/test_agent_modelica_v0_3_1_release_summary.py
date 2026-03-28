from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_1_release_summary import build_v0_3_1_release_summary


class AgentModelicaV031ReleaseSummaryTests(unittest.TestCase):
    def test_staged_completion_passes_when_external_cli_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v031_release_") as td:
            root = Path(td)
            block_paths = {}
            for block_id in [
                "block_0_v0_3_0_seal",
                "block_1_structural_singularity_trial",
                "block_2_layer4_holdout_pack",
                "block_3_harder_holdout_ablation",
            ]:
                path = root / f"{block_id}.json"
                path.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
                block_paths[block_id] = str(path)
            external_path = root / "block_4_external_mcp_surface.json"
            external_path.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "classification": "blocked_external_cli_mcp_tool_plane",
                        "live_comparison_ready": False,
                    }
                ),
                encoding="utf-8",
            )
            block_paths["block_4_external_mcp_surface"] = str(external_path)
            block_paths["block_5_track_c_live_matrix"] = str(root / "missing_claim_gate.json")
            payload = build_v0_3_1_release_summary(
                out_dir=str(root / "out"),
                blocks=[{"block_id": key, "summary_path": value} for key, value in block_paths.items()],
            )
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["completion_mode"], "staged_internal_complete_external_blocked")
            rows = {row["block_id"]: row["status"] for row in payload["blocks"]}
            self.assertEqual(rows["block_4_external_mcp_surface"], "BLOCKED_EXTERNAL")
            self.assertEqual(rows["block_5_track_c_live_matrix"], "DEFERRED_EXTERNAL")


if __name__ == "__main__":
    unittest.main()
