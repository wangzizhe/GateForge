from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_external_agent_live_runner_v0_3_1 import (
    _build_claude_command,
    _build_codex_add_command,
    _build_codex_exec_command,
    _build_codex_remove_command,
    _claude_mcp_config,
    _run_subprocess,
    _server_command,
)


SCHEMA_VERSION = "agent_modelica_external_agent_mcp_probe_v0_3_1"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_external_agent_mcp_probe_v0_3_1"
DEFAULT_DOCKER_IMAGE = "openmodelica/openmodelica:v1.24.4-ompython"


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "ok": {"type": "boolean"},
            "tool_name": {"type": "string"},
            "tool_used": {"type": "boolean"},
            "note": {"type": "string"},
        },
        "required": ["ok", "tool_name", "tool_used", "note"],
        "additionalProperties": False,
    }


def _prompt(tool_name: str) -> str:
    return "\n".join(
        [
            "Use the shared OpenModelica MCP tool plane.",
            f"Call `{tool_name}` exactly once.",
            "Do not use shell, file editing, or any non-MCP path.",
            "After the MCP call, return only JSON matching the required schema.",
            f"Set `tool_name` to `{tool_name}` and `tool_used` to true only if you actually called it.",
        ]
    )


def _extract_probe_payload(text: str) -> dict:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            if "structured_output" in payload and isinstance(payload["structured_output"], dict):
                return dict(payload["structured_output"])
            return payload
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            payload = json.loads(raw[start : end + 1])
        except Exception:
            return {}
        if isinstance(payload, dict):
            if "structured_output" in payload and isinstance(payload["structured_output"], dict):
                return dict(payload["structured_output"])
            return payload
    return {}


def run_probe(
    *,
    provider_name: str,
    tool_name: str = "omc_get_error_string",
    out_dir: str = DEFAULT_OUT_DIR,
    model_id: str = "",
    docker_image: str = DEFAULT_DOCKER_IMAGE,
    timeout_sec: int = 120,
    use_global_server_name: str = "",
) -> dict:
    provider = str(provider_name).strip().lower()
    if provider not in {"claude", "codex"}:
        raise ValueError(f"unsupported_provider:{provider_name}")
    out_root = Path(out_dir)
    schema_path = out_root / "response_schema.json"
    _write_json(schema_path, _schema())
    prompt = _prompt(tool_name)
    _write_text(out_root / "prompt.txt", prompt)
    ledger_path = out_root / "mcp_ledger.json"
    server_name = str(use_global_server_name or "omc").strip()
    server_cmd = _server_command(
        docker_image=docker_image,
        artifact_root=str(out_root / "mcp_artifacts"),
        ledger_path=str(ledger_path),
    )

    started = time.time()
    stdout = ""
    stderr = ""
    payload: dict = {}
    timed_out = False
    try:
        if provider == "claude":
            mcp_config_path = ""
            if not use_global_server_name:
                mcp_config_path = str((out_root / "claude_mcp.json").resolve())
                _write_json(mcp_config_path, _claude_mcp_config(server_cmd))
            cmd = _build_claude_command(
                prompt=prompt,
                mcp_config_path=str(mcp_config_path),
                output_schema_path=str(schema_path.resolve()),
                model_id=model_id,
                server_name=server_name,
            )
            proc = _run_subprocess(cmd, timeout_sec=int(timeout_sec))
            stdout = str(proc.stdout or "")
            stderr = str(proc.stderr or "")
        else:
            added_here = False
            if not use_global_server_name:
                server_name = f"gateforge_probe_{uuid.uuid4().hex[:8]}"
                added_here = True
            add_proc = None
            if added_here:
                add_proc = _run_subprocess(_build_codex_add_command(server_name=server_name, server_cmd=server_cmd), timeout_sec=30)
            else:
                add_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            stdout += str(add_proc.stdout or "")
            stderr += str(add_proc.stderr or "")
            if add_proc.returncode == 0:
                last_message_path = out_root / "codex_last_message.json"
                exec_proc = _run_subprocess(
                    _build_codex_exec_command(
                        prompt=prompt,
                        output_schema_path=str(schema_path.resolve()),
                        last_message_path=str(last_message_path),
                        model_id=model_id,
                        cwd=str(Path.cwd()),
                    ),
                    timeout_sec=int(timeout_sec),
                )
                stdout += ("\n" + str(exec_proc.stdout or "")).strip()
                stderr += ("\n" + str(exec_proc.stderr or "")).strip()
                if last_message_path.exists():
                    payload = _extract_probe_payload(last_message_path.read_text(encoding="utf-8"))
                if added_here:
                    _run_subprocess(_build_codex_remove_command(server_name=server_name), timeout_sec=30)
    except subprocess.TimeoutExpired:
        timed_out = True

    if not payload:
        payload = _extract_probe_payload(stdout)
    _write_text(out_root / "provider_stdout.txt", stdout)
    _write_text(out_root / "provider_stderr.txt", stderr)

    ledger = _load_json(ledger_path)
    tool_call_count = int(ledger.get("tool_call_count") or 0)
    tool_names = [
        str(row.get("tool_name") or "")
        for row in (ledger.get("records") or [])
        if isinstance(row, dict) and str(row.get("tool_name") or "").strip()
    ]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "provider_name": provider,
        "tool_name": str(tool_name),
        "tool_call_count": tool_call_count,
        "tool_names": tool_names,
        "provider_wall_clock_sec": round(time.time() - started, 2),
        "timed_out": bool(timed_out),
        "provider_payload": payload,
        "shared_tool_plane_reached": tool_call_count > 0,
    }
    _write_json(out_root / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe whether an external provider can actually call the shared OMC MCP tool plane.")
    parser.add_argument("--provider", choices=["claude", "codex"], required=True)
    parser.add_argument("--tool-name", default="omc_get_error_string")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--model-id", default="")
    parser.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument("--use-global-server-name", default="")
    args = parser.parse_args()
    payload = run_probe(
        provider_name=str(args.provider),
        tool_name=str(args.tool_name),
        out_dir=str(args.out_dir),
        model_id=str(args.model_id),
        docker_image=str(args.docker_image),
        timeout_sec=int(args.timeout_sec),
        use_global_server_name=str(args.use_global_server_name),
    )
    print(json.dumps({"status": payload.get("status"), "shared_tool_plane_reached": bool(payload.get("shared_tool_plane_reached"))}))


if __name__ == "__main__":
    main()
