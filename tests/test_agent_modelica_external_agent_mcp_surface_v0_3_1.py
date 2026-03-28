from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_external_agent_mcp_surface_v0_3_1 import (
    build_external_agent_mcp_surface_summary,
)


class AgentModelicaExternalAgentMcpSurfaceV031Tests(unittest.TestCase):
    def test_classifies_external_cli_no_jsonrpc_handshake(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_mcp_surface_") as td:
            root = Path(td)
            probe_dirs = []
            for provider in ["claude", "codex"]:
                probe_dir = root / provider
                probe_dirs.append(str(probe_dir / "summary.json"))
                probe_dir.mkdir(parents=True, exist_ok=True)
                (probe_dir / "summary.json").write_text(
                    json.dumps(
                        {
                            "provider_name": provider,
                            "status": "PASS",
                            "shared_tool_plane_reached": False,
                        }
                    ),
                    encoding="utf-8",
                )
                (probe_dir / "mcp_protocol_trace.jsonl").write_text(
                    "\n".join(
                        [
                            json.dumps({"event": "launcher_start"}),
                            json.dumps({"event": "launcher_import_ok"}),
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
            payload = build_external_agent_mcp_surface_summary(
                probe_summary_paths=probe_dirs,
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["classification"], "blocked_external_cli_mcp_tool_plane")
            self.assertFalse(payload["live_comparison_ready"])


if __name__ == "__main__":
    unittest.main()
