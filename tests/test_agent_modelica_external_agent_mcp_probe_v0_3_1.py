from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_external_agent_mcp_probe_v0_3_1 import (
    _extract_probe_payload,
    run_probe,
)


class AgentModelicaExternalAgentMcpProbeV031Tests(unittest.TestCase):
    def test_extract_probe_payload_reads_structured_output_wrapper(self) -> None:
        payload = _extract_probe_payload('{"type":"result","structured_output":{"ok":true,"tool_name":"omc_get_error_string","tool_used":true,"note":"x"}}')
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["tool_name"], "omc_get_error_string")

    def test_run_probe_marks_shared_plane_when_ledger_has_tool_call(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_probe_") as td:
            root = Path(td)

            def _fake_run(cmd, *, timeout_sec):
                if cmd[0] == "claude":
                    ledger = root / "out" / "mcp_ledger.json"
                    ledger.write_text(
                        json.dumps({"tool_call_count": 1, "records": [{"tool_name": "omc_get_error_string"}]}),
                        encoding="utf-8",
                    )
                    return mock.Mock(
                        returncode=0,
                        stdout='{"type":"result","structured_output":{"ok":true,"tool_name":"omc_get_error_string","tool_used":true,"note":"ok"}}',
                        stderr="",
                    )
                raise AssertionError(cmd)

            with mock.patch("gateforge.agent_modelica_external_agent_mcp_probe_v0_3_1._run_subprocess", side_effect=_fake_run):
                summary = run_probe(provider_name="claude", out_dir=str(root / "out"), timeout_sec=10)
            self.assertTrue(summary["shared_tool_plane_reached"])
            self.assertEqual(summary["tool_call_count"], 1)

    def test_run_probe_can_use_global_server_mode_without_local_mcp_config(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_probe_") as td:
            root = Path(td)

            def _fake_run(cmd, *, timeout_sec):
                self.assertEqual(cmd[0], "claude")
                self.assertNotIn("--mcp-config", cmd)
                return mock.Mock(
                    returncode=0,
                    stdout='{"structured_output":{"ok":false,"tool_name":"omc_get_error_string","tool_used":false,"note":"x"}}',
                    stderr="",
                )

            with mock.patch("gateforge.agent_modelica_external_agent_mcp_probe_v0_3_1._run_subprocess", side_effect=_fake_run):
                summary = run_probe(
                    provider_name="claude",
                    out_dir=str(root / "out"),
                    timeout_sec=10,
                    use_global_server_name="gateforge_global",
                )
            self.assertFalse(summary["shared_tool_plane_reached"])


if __name__ == "__main__":
    unittest.main()
