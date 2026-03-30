from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_diagnostic_ir_v0 import build_diagnostic_ir_v0
from .agent_modelica_omc_workspace_v1 import (
    extract_om_success_flags,
    prepare_workspace_model_layout,
    run_omc_script_docker,
    run_omc_script_local,
    temporary_workspace,
)


SCHEMA_VERSION = "agent_modelica_omc_mcp_server_v1"
TOOL_NAMES = (
    "omc_check_model",
    "omc_simulate_model",
    "omc_get_error_string",
    "omc_read_artifact",
)


def _norm(value: object) -> str:
    return str(value or "").strip()


def _artifact_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:10]


def _fallback_model_path(model_name: str, source_file_name: str = "") -> Path:
    file_name = _norm(source_file_name)
    if file_name:
        return Path(file_name)
    stem = (_norm(model_name).split(".")[-1] or "model").strip()
    return Path(f"{stem}.mo")


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _append_jsonl(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _tool_defs() -> list[dict]:
    return [
        {
            "name": "omc_check_model",
            "description": "Run OpenModelica checkModel on a candidate Modelica text and return compiler diagnostics.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "model_text": {"type": "string"},
                    "model_name": {"type": "string"},
                    "source_file_name": {"type": "string"},
                    "source_library_path": {"type": "string"},
                    "source_package_name": {"type": "string"},
                    "source_library_model_path": {"type": "string"},
                    "source_qualified_model_name": {"type": "string"},
                    "extra_model_loads": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["model_text", "model_name"],
            },
        },
        {
            "name": "omc_simulate_model",
            "description": "Run OpenModelica simulate on a candidate Modelica text and return runtime diagnostics.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "model_text": {"type": "string"},
                    "model_name": {"type": "string"},
                    "source_file_name": {"type": "string"},
                    "source_library_path": {"type": "string"},
                    "source_package_name": {"type": "string"},
                    "source_library_model_path": {"type": "string"},
                    "source_qualified_model_name": {"type": "string"},
                    "extra_model_loads": {"type": "array", "items": {"type": "string"}},
                    "stop_time": {"type": "number"},
                    "intervals": {"type": "integer"},
                },
                "required": ["model_text", "model_name"],
            },
        },
        {
            "name": "omc_get_error_string",
            "description": "Return the latest OpenModelica error string observed by this MCP server session.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "omc_read_artifact",
            "description": "Read a bounded text slice from a server-created artifact path.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "artifact_path": {"type": "string"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["artifact_path"],
            },
        },
    ]


class OmcMcpServer:
    def __init__(
        self,
        *,
        backend: str,
        docker_image: str,
        timeout_sec: int,
        artifact_root: str,
        default_stop_time: float,
        default_intervals: int,
        ledger_path: str = "",
        protocol_trace_path: str = "",
    ) -> None:
        self.backend = str(backend)
        self.docker_image = str(docker_image)
        self.timeout_sec = int(timeout_sec)
        self.default_stop_time = float(default_stop_time)
        self.default_intervals = int(default_intervals)
        self.artifact_root = Path(artifact_root)
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.ledger_path = Path(ledger_path) if str(ledger_path).strip() else self.artifact_root / "tool_ledger.json"
        self.protocol_trace_path = Path(protocol_trace_path) if str(protocol_trace_path).strip() else None
        self.latest_error_string = ""
        self._ledger: list[dict] = []

    def _persist_ledger(self) -> None:
        _write_json(
            self.ledger_path,
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "tool_call_count": len(self._ledger),
                "records": self._ledger,
            },
        )

    def _record_call(self, *, tool_name: str, arguments: dict, result: dict) -> None:
        self._ledger.append(
            {
                "tool_name": str(tool_name),
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "arguments": dict(arguments),
                "result": dict(result),
            }
        )
        self._persist_ledger()

    def trace_protocol(self, *, direction: str, message: dict) -> None:
        if self.protocol_trace_path is None:
            return
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        _append_jsonl(
            self.protocol_trace_path,
            {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "direction": str(direction),
                "method": _norm(message.get("method")),
                "id": message.get("id"),
                "jsonrpc": _norm(message.get("jsonrpc")),
                "params_keys": sorted(params.keys()),
                "tool_name": _norm(params.get("name")),
            },
        )

    def _run_script(self, script_text: str, *, cwd: str) -> tuple[int | None, str]:
        if self.backend == "omc":
            return run_omc_script_local(script_text, timeout_sec=self.timeout_sec, cwd=cwd)
        return run_omc_script_docker(script_text, timeout_sec=self.timeout_sec, cwd=cwd, image=self.docker_image)

    def _workspace_layout(self, arguments: dict):
        model_name = _norm(arguments.get("model_name"))
        return prepare_workspace_model_layout(
            workspace=arguments["_workspace"],
            fallback_model_path=_fallback_model_path(model_name, _norm(arguments.get("source_file_name"))),
            primary_model_name=model_name,
            source_library_path=_norm(arguments.get("source_library_path")),
            source_package_name=_norm(arguments.get("source_package_name")),
            source_library_model_path=_norm(arguments.get("source_library_model_path")),
            source_qualified_model_name=_norm(arguments.get("source_qualified_model_name")),
        )

    def _bootstrap(self, extra_model_loads: list[str]) -> str:
        bootstrap = "loadModel(Modelica);\n" if self.backend == "omc" else "installPackage(Modelica);\nloadModel(Modelica);\n"
        if extra_model_loads:
            bootstrap += "".join(f"loadModel({item});\n" for item in extra_model_loads if _norm(item))
        return bootstrap

    def _artifact_dir(self, tool_name: str) -> Path:
        path = self.artifact_root / tool_name / _artifact_id()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _call_check_or_simulate(self, tool_name: str, arguments: dict) -> dict:
        model_text = _norm(arguments.get("model_text"))
        model_name = _norm(arguments.get("model_name"))
        if not model_text or not model_name:
            return {"ok": False, "error_message": "model_text_and_model_name_required"}
        extra_model_loads = [str(x) for x in (arguments.get("extra_model_loads") or []) if _norm(x)]
        stop_time = float(arguments.get("stop_time") or self.default_stop_time)
        intervals = int(arguments.get("intervals") or self.default_intervals)
        artifact_dir = self._artifact_dir(tool_name)

        with temporary_workspace(prefix="gf_omc_mcp_") as td:
            workspace = Path(td)
            workspace_args = dict(arguments)
            workspace_args["_workspace"] = workspace
            layout = self._workspace_layout(workspace_args)
            layout.model_write_path.parent.mkdir(parents=True, exist_ok=True)
            layout.model_write_path.write_text(model_text, encoding="utf-8")
            load_lines = "".join(f'loadFile("{item}");\n' for item in layout.model_load_files if _norm(item))
            if tool_name == "omc_check_model":
                script = self._bootstrap(extra_model_loads) + load_lines + f"checkModel({layout.model_identifier});\ngetErrorString();\n"
            else:
                script = (
                    self._bootstrap(extra_model_loads)
                    + load_lines
                    + f"checkModel({layout.model_identifier});\n"
                    + f"simulate({layout.model_identifier}, stopTime={float(stop_time)}, numberOfIntervals={int(intervals)});\n"
                    + "getErrorString();\n"
                )
            rc, output = self._run_script(script, cwd=str(workspace))
            check_ok, simulate_ok = extract_om_success_flags(output)
            diag = build_diagnostic_ir_v0(
                output=output,
                check_model_pass=bool(check_ok),
                simulate_pass=bool(simulate_ok),
                expected_stage="check" if tool_name == "omc_check_model" else "simulate",
                declared_failure_type="",
            )
            self.latest_error_string = str(output or "")
            log_path = artifact_dir / "omc_output.txt"
            _write_text(log_path, str(output or ""))
            response = {
                "ok": bool(check_ok) if tool_name == "omc_check_model" else bool(check_ok and simulate_ok),
                "model_name": model_name,
                "return_code": rc,
                "check_model_pass": bool(check_ok),
                "simulate_pass": bool(simulate_ok) if tool_name == "omc_simulate_model" else None,
                "error_type": str(diag.get("error_type") or ""),
                "reason": str(diag.get("reason") or ""),
                "error_message": str(output or "")[:1000],
                "stderr_snippet": str(output or "")[-400:],
                "artifact_path": str(log_path.resolve()),
            }
            self._record_call(tool_name=tool_name, arguments={k: v for k, v in arguments.items() if k != "model_text"}, result=response)
            return response

    def call_tool(self, tool_name: str, arguments: dict | None = None) -> dict:
        args = dict(arguments or {})
        if tool_name == "omc_check_model":
            return self._call_check_or_simulate(tool_name, args)
        if tool_name == "omc_simulate_model":
            return self._call_check_or_simulate(tool_name, args)
        if tool_name == "omc_get_error_string":
            result = {"error_string": self.latest_error_string}
            self._record_call(tool_name=tool_name, arguments=args, result=result)
            return result
        if tool_name == "omc_read_artifact":
            artifact_path = Path(_norm(args.get("artifact_path")))
            max_chars = max(1, int(args.get("max_chars") or 4000))
            try:
                artifact_path.relative_to(self.artifact_root)
            except Exception:
                result = {"content": "", "truncated": False, "error_message": "artifact_path_outside_server_root"}
                self._record_call(tool_name=tool_name, arguments=args, result=result)
                return result
            if not artifact_path.exists():
                result = {"content": "", "truncated": False, "error_message": "artifact_missing"}
                self._record_call(tool_name=tool_name, arguments=args, result=result)
                return result
            content = artifact_path.read_text(encoding="utf-8")
            result = {"content": content[:max_chars], "truncated": len(content) > max_chars}
            self._record_call(tool_name=tool_name, arguments=args, result=result)
            return result
        raise ValueError(f"unknown_tool:{tool_name}")


def _read_message() -> dict | None:
    # MCP stdio transport uses newline-delimited JSON (one JSON object per line).
    # Some older / manual callers use Content-Length framing (LSP-style).
    # We support both: if the first non-empty line starts with '{' it is raw JSON;
    # otherwise we fall through to the header-parsing path.
    first_line = sys.stdin.buffer.readline()
    if not first_line:
        return None
    stripped = first_line.strip()
    if stripped.startswith(b"{"):
        # Raw newline-delimited JSON (Claude Code / MCP spec path)
        try:
            return json.loads(stripped.decode("utf-8"))
        except json.JSONDecodeError:
            return None
    # Content-Length framing path (backward-compatible with manual test callers)
    headers: dict[str, str] = {}
    text = stripped.decode("utf-8")
    if text and ":" in text:
        k, v = text.split(":", 1)
        headers[k.strip().lower()] = v.strip()
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in {b"\r\n", b"\n"}:
            break
        text = line.decode("utf-8").strip()
        if ":" in text:
            k, v = text.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    length = int(headers.get("content-length") or 0)
    if length <= 0:
        return None
    payload = sys.stdin.buffer.read(length)
    if not payload:
        return None
    return json.loads(payload.decode("utf-8"))


def _write_message(payload: dict) -> None:
    # Send newline-delimited JSON to match the MCP stdio transport spec.
    # Claude Code expects this format; Content-Length framing is not used here.
    raw = json.dumps(payload, separators=(",", ":"))
    sys.stdout.buffer.write((raw + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def _result_response(message_id: object, result: object) -> dict:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _error_response(message_id: object, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def serve_stdio(server: OmcMcpServer, *, startup_eof_grace_sec: float = 2.0) -> None:
    saw_first_message = False
    startup_eof_deadline: float | None = None
    while True:
        message = _read_message()
        if message is None:
            if not saw_first_message and float(startup_eof_grace_sec or 0.0) > 0.0:
                if startup_eof_deadline is None:
                    startup_eof_deadline = time.monotonic() + float(startup_eof_grace_sec)
                remaining = startup_eof_deadline - time.monotonic()
                if remaining > 0.0:
                    time.sleep(min(0.05, remaining))
                    continue
            return
        saw_first_message = True
        startup_eof_deadline = None
        server.trace_protocol(direction="in", message=message)
        method = _norm(message.get("method"))
        message_id = message.get("id")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        if method == "initialize":
            client_protocol = _norm(params.get("protocolVersion")) or "2024-11-05"
            response = _result_response(
                message_id,
                {
                    "protocolVersion": client_protocol,
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                        "prompts": {"listChanged": False},
                    },
                    "serverInfo": {"name": SCHEMA_VERSION, "version": "1"},
                },
            )
            server.trace_protocol(direction="out", message=response)
            _write_message(response)
            continue
        if method == "notifications/initialized":
            continue
        if method == "ping":
            response = _result_response(message_id, {})
            server.trace_protocol(direction="out", message=response)
            _write_message(response)
            continue
        if method == "tools/list":
            response = _result_response(message_id, {"tools": _tool_defs()})
            server.trace_protocol(direction="out", message=response)
            _write_message(response)
            continue
        if method == "resources/list":
            response = _result_response(message_id, {"resources": []})
            server.trace_protocol(direction="out", message=response)
            _write_message(response)
            continue
        if method == "resources/templates/list":
            response = _result_response(message_id, {"resourceTemplates": []})
            server.trace_protocol(direction="out", message=response)
            _write_message(response)
            continue
        if method == "prompts/list":
            response = _result_response(message_id, {"prompts": []})
            server.trace_protocol(direction="out", message=response)
            _write_message(response)
            continue
        if method == "tools/call":
            name = _norm(params.get("name"))
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            try:
                result = server.call_tool(name, arguments)
            except Exception as exc:
                response = _error_response(message_id, -32000, f"{type(exc).__name__}:{exc}")
                server.trace_protocol(direction="out", message=response)
                _write_message(response)
                continue
            response = _result_response(message_id, {"content": [{"type": "text", "text": json.dumps(result)}], "isError": False})
            server.trace_protocol(direction="out", message=response)
            _write_message(response)
            continue
        if message_id is not None:
            response = _error_response(message_id, -32601, f"unsupported_method:{method}")
            server.trace_protocol(direction="out", message=response)
            _write_message(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a minimal OpenModelica MCP stdio server for Track C.")
    parser.add_argument("--backend", choices=["omc", "openmodelica_docker"], default="openmodelica_docker")
    parser.add_argument("--docker-image", default="openmodelica/openmodelica:v1.24.4-ompython")
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument("--artifact-root", default="/tmp/agent_modelica_omc_mcp_server_v1")
    parser.add_argument("--default-stop-time", type=float, default=1.0)
    parser.add_argument("--default-intervals", type=int, default=500)
    parser.add_argument("--ledger-path", default="")
    parser.add_argument("--protocol-trace-path", default="")
    parser.add_argument("--startup-eof-grace-sec", type=float, default=2.0)
    args = parser.parse_args()
    serve_stdio(
        OmcMcpServer(
            backend=str(args.backend),
            docker_image=str(args.docker_image),
            timeout_sec=int(args.timeout_sec),
            artifact_root=str(args.artifact_root),
            default_stop_time=float(args.default_stop_time),
            default_intervals=int(args.default_intervals),
            ledger_path=str(args.ledger_path),
            protocol_trace_path=str(args.protocol_trace_path),
        ),
        startup_eof_grace_sec=float(args.startup_eof_grace_sec),
    )


if __name__ == "__main__":
    main()
