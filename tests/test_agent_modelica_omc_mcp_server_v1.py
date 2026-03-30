from __future__ import annotations

import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_omc_mcp_server_v1 import OmcMcpServer


class AgentModelicaOmcMcpServerV1Tests(unittest.TestCase):
    def test_check_tool_writes_artifact_and_updates_error_string(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_omc_mcp_") as td:
            root = Path(td)
            server = OmcMcpServer(
                backend="omc",
                docker_image="unused",
                timeout_sec=30,
                artifact_root=str(root / "artifacts"),
                default_stop_time=1.0,
                default_intervals=500,
                ledger_path=str(root / "ledger.json"),
            )
            with mock.patch(
                "gateforge.agent_modelica_omc_mcp_server_v1.run_omc_script_local",
                return_value=(0, "true\n\"Check of M completed successfully.\""),
            ):
                result = server.call_tool(
                    "omc_check_model",
                    {
                        "model_text": "model M end M;",
                        "model_name": "M",
                    },
                )
            self.assertTrue(result["ok"])
            self.assertTrue(Path(result["artifact_path"]).exists())
            self.assertIn("completed successfully", server.latest_error_string)
            ledger = json.loads((root / "ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["tool_call_count"], 1)

    def test_read_artifact_rejects_path_outside_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_omc_mcp_") as td:
            root = Path(td)
            server = OmcMcpServer(
                backend="omc",
                docker_image="unused",
                timeout_sec=30,
                artifact_root=str(root / "artifacts"),
                default_stop_time=1.0,
                default_intervals=500,
                ledger_path=str(root / "ledger.json"),
            )
            result = server.call_tool("omc_read_artifact", {"artifact_path": str(root / "elsewhere.txt")})
            self.assertEqual(result["error_message"], "artifact_path_outside_server_root")

    def test_protocol_trace_records_initialize_and_tools_list(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_omc_mcp_trace_") as td:
            root = Path(td)
            trace_path = root / "trace.jsonl"
            cmd = [
                "python3",
                "-m",
                "gateforge.agent_modelica_omc_mcp_server_v1",
                "--backend",
                "omc",
                "--artifact-root",
                str(root / "artifacts"),
                "--ledger-path",
                str(root / "ledger.json"),
                "--protocol-trace-path",
                str(trace_path),
            ]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            def _send(payload: dict) -> None:
                raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                assert proc.stdin is not None
                proc.stdin.write(raw + b"\n")
                proc.stdin.flush()

            def _recv() -> dict:
                assert proc.stdout is not None
                line = proc.stdout.readline()
                self.assertTrue(line)
                return json.loads(line.decode("utf-8"))

            try:
                _send(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1"},
                        },
                    }
                )
                _recv()
                _send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
                _send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
                _recv()
            finally:
                proc.terminate()
                proc.wait(timeout=5)
                if proc.stdin is not None:
                    proc.stdin.close()
                if proc.stdout is not None:
                    proc.stdout.close()
                if proc.stderr is not None:
                    proc.stderr.close()

            rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            methods = [(row["direction"], row["method"]) for row in rows]
            response_ids = {row.get("id") for row in rows if row.get("direction") == "out"}
            self.assertIn(("in", "initialize"), methods)
            self.assertIn(("in", "tools/list"), methods)
            self.assertIn(1, response_ids)
            self.assertIn(2, response_ids)

    def test_server_does_not_exit_immediately_on_startup_eof(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_omc_mcp_eof_") as td:
            root = Path(td)
            cmd = [
                "python3",
                "-m",
                "gateforge.agent_modelica_omc_mcp_server_v1",
                "--backend",
                "omc",
                "--artifact-root",
                str(root / "artifacts"),
                "--ledger-path",
                str(root / "ledger.json"),
                "--startup-eof-grace-sec",
                "0.5",
            ]
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                time.sleep(0.15)
                self.assertIsNone(proc.poll())
                time.sleep(0.55)
                self.assertIsNotNone(proc.poll())
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=5)
                if proc.stdout is not None:
                    proc.stdout.close()
                if proc.stderr is not None:
                    proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
