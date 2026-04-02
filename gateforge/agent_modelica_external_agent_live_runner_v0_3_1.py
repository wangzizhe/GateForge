from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_external_agent_runner_v1 import normalize_external_agent_run
from .agent_modelica_omc_mcp_server_v1 import OmcMcpServer
from .agent_modelica_prompt_surface_v1 import build_external_agent_repair_prompt


SCHEMA_VERSION = "agent_modelica_external_agent_live_runner_v0_3_1"
DEFAULT_TASKSET = "artifacts/agent_modelica_layer4_holdout_v0_3_1/taskset_frozen.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_external_agent_live_runner_v0_3_1"
DEFAULT_BUDGET = "artifacts/agent_modelica_v0_3_0_seal_v1/summary.json"
DEFAULT_DOCKER_IMAGE = "openmodelica/openmodelica:v1.24.4-ompython"
SUPPORTED_EXTERNAL_PROVIDERS = ("claude", "codex")


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _model_name(task: dict) -> str:
    meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
    qualified = _norm(meta.get("qualified_model_name"))
    if qualified:
        return qualified
    source_model_path = Path(_norm(task.get("source_model_path") or task.get("mutated_model_path")))
    return source_model_path.stem or "Model"


def _package_name(task: dict) -> str:
    meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
    package = _norm(meta.get("package_name"))
    if package:
        return package
    qualified = _model_name(task)
    if "." in qualified:
        return qualified.split(".", 1)[0].strip()
    return ""


def _task_context(task: dict) -> dict:
    meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
    mutated_path = Path(_norm(task.get("mutated_model_path")))
    mutated_text = mutated_path.read_text(encoding="utf-8") if mutated_path.exists() else ""
    extra_model_loads: list[str] = []
    package_name = _package_name(task)
    if package_name and package_name not in {"Modelica"}:
        extra_model_loads.append(package_name)
    return {
        "task_id": _norm(task.get("task_id")),
        "failure_type": _norm(task.get("failure_type")),
        "expected_stage": _norm(task.get("expected_stage")),
        "model_name": _model_name(task),
        "model_text": mutated_text,
        "source_file_name": mutated_path.name if mutated_path.exists() else f"{_model_name(task).split('.')[-1]}.mo",
        "source_library_path": _norm(meta.get("accepted_source_path") or meta.get("local_path")),
        "source_package_name": package_name,
        "source_library_model_path": _norm(meta.get("model_path")),
        "source_qualified_model_name": _norm(meta.get("qualified_model_name")),
        "extra_model_loads": extra_model_loads,
    }


def _load_tasks(path: str) -> list[dict]:
    payload = _load_json(path)
    rows = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    return [dict(row) for row in rows if isinstance(row, dict) and _norm(row.get("task_id"))]


def _budget_from_seal(path: str) -> dict:
    payload = _load_json(path)
    auth = payload.get("track_c_budget_authority") if isinstance(payload.get("track_c_budget_authority"), dict) else {}
    return dict(auth.get("recommended_budget") or {})


def _output_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "task_status": {"type": "string", "enum": ["PASS", "FAIL", "BUDGET_EXHAUSTED"]},
            "budget_exhausted": {"type": "boolean"},
            "rounds_used_estimate": {"type": "integer"},
            "patched_model_text": {"type": "string"},
            "repair_rationale": {"type": "string"},
        },
        "required": ["task_status", "budget_exhausted", "rounds_used_estimate", "patched_model_text", "repair_rationale"],
        "additionalProperties": False,
    }


def _arm_prompt(task_ctx: dict, *, arm_id: str, budget: dict) -> str:
    return build_external_agent_repair_prompt(task_ctx=task_ctx, arm_id=arm_id, budget=budget)


def _task_infra_reason(text: str) -> str:
    lower = str(text or "").lower()
    if "lookup address information" in lower or "could not resolve host" in lower or "dns" in lower:
        return "network_unavailable"
    if "api key" in lower or "not logged in" in lower or "authentication" in lower or "login" in lower:
        return "provider_auth_unavailable"
    if "mcp" in lower and ("failed" in lower or "unavailable" in lower):
        return "mcp_server_unavailable"
    return "provider_command_nonzero"


def _extract_json_payload(text: str) -> dict:
    def _looks_like_agent_payload(payload: dict) -> bool:
        keys = set(payload.keys())
        return {
            "task_status",
            "budget_exhausted",
            "rounds_used_estimate",
            "patched_model_text",
            "repair_rationale",
        }.issubset(keys)

    def _search(value: object) -> dict:
        if isinstance(value, dict):
            if _looks_like_agent_payload(value):
                return value
            for nested in value.values():
                found = _search(nested)
                if found:
                    return found
            return {}
        if isinstance(value, list):
            for item in value:
                found = _search(item)
                if found:
                    return found
            return {}
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    nested = json.loads(stripped)
                except Exception:
                    return {}
                return _search(nested)
        return {}

    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
        found = _search(payload)
        if found:
            return found
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            payload = json.loads(raw[start : end + 1])
        except Exception:
            return {}
        found = _search(payload)
        return found if found else {}
    return {}


def _provider_mcp_config(server_cmd: list[str]) -> dict:
    return {
        "mcpServers": {
            "omc": {
                "command": server_cmd[0],
                "args": server_cmd[1:],
            }
        }
    }


def _python_executable() -> str:
    return sys.executable or "python3"


def _server_command(*, docker_image: str, artifact_root: str, ledger_path: str) -> list[str]:
    protocol_trace_path = str((Path(artifact_root).parent / "mcp_protocol_trace.jsonl").resolve())
    launcher_path = str((Path(__file__).resolve().parents[1] / "scripts" / "launch_agent_modelica_omc_mcp_server_v1.py").resolve())
    return [
        _python_executable(),
        launcher_path,
        "--backend",
        "openmodelica_docker",
        "--docker-image",
        str(docker_image),
        "--artifact-root",
        str(Path(artifact_root).resolve()),
        "--ledger-path",
        str(Path(ledger_path).resolve()),
        "--protocol-trace-path",
        protocol_trace_path,
    ]


def _build_provider_inline_mcp_command(
    *,
    provider_name: str,
    prompt: str,
    mcp_config_path: str,
    output_schema_path: str,
    model_id: str,
    server_name: str = "omc",
) -> list[str]:
    provider = _norm(provider_name).lower()
    if provider != "claude":
        raise ValueError(f"inline_mcp_config_unsupported_provider:{provider_name}")
    allowed_tools = ",".join(
        [
            f"mcp__{server_name}__omc_check_model",
            f"mcp__{server_name}__omc_simulate_model",
            f"mcp__{server_name}__omc_get_error_string",
            f"mcp__{server_name}__omc_read_artifact",
        ]
    )
    cmd = [
        provider,
        "-p",
        "--output-format",
        "json",
        "--permission-mode",
        "bypassPermissions",
        "--allowedTools",
        allowed_tools,
        "--json-schema",
        Path(output_schema_path).read_text(encoding="utf-8"),
        *(["--model", str(model_id)] if _norm(model_id) else []),
        prompt,
    ]
    if str(mcp_config_path).strip():
        cmd[8:8] = ["--mcp-config", str(mcp_config_path), "--strict-mcp-config"]
    return cmd


def _build_provider_registered_server_add_command(
    *, provider_name: str, server_name: str, server_cmd: list[str]
) -> list[str]:
    provider = _norm(provider_name).lower()
    if provider != "codex":
        raise ValueError(f"registered_server_add_unsupported_provider:{provider_name}")
    return [
        provider,
        "mcp",
        "add",
        str(server_name),
        "--",
        *server_cmd,
    ]


def _build_provider_registered_server_remove_command(*, provider_name: str, server_name: str) -> list[str]:
    provider = _norm(provider_name).lower()
    if provider != "codex":
        raise ValueError(f"registered_server_remove_unsupported_provider:{provider_name}")
    return [provider, "mcp", "remove", str(server_name)]


def _build_provider_registered_server_exec_command(
    *,
    provider_name: str,
    prompt: str,
    output_schema_path: str,
    last_message_path: str,
    model_id: str,
    cwd: str,
) -> list[str]:
    provider = _norm(provider_name).lower()
    if provider != "codex":
        raise ValueError(f"registered_server_exec_unsupported_provider:{provider_name}")
    cmd = [
        provider,
        "exec",
        "--skip-git-repo-check",
        "-C",
        str(cwd),
        # MCP tool calls require full-access mode; read-only sandbox blocks them
        # even when approval=never is set in config.toml.
        "--dangerously-bypass-approvals-and-sandbox",
        "--output-schema",
        str(output_schema_path),
        "-o",
        str(last_message_path),
    ]
    if _norm(model_id):
        cmd += ["-m", str(model_id)]
    cmd += [prompt]
    return cmd


def _append_provider_server_hint(*, provider_name: str, prompt: str, server_name: str) -> str:
    provider = _norm(provider_name).lower()
    if provider == "codex":
        return prompt + f"\n\nIMPORTANT: Use only the MCP server named `{server_name}` for all OpenModelica tool calls."
    return prompt


def _run_subprocess(cmd: list[str], *, timeout_sec: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=max(30, int(timeout_sec)), check=False)


def _verify_candidate(
    *,
    task_ctx: dict,
    candidate_text: str,
    docker_image: str,
    artifact_root: str,
) -> dict:
    server = OmcMcpServer(
        backend="openmodelica_docker",
        docker_image=str(docker_image),
        timeout_sec=120,
        artifact_root=str(Path(artifact_root) / "verification"),
        default_stop_time=1.0,
        default_intervals=500,
        ledger_path=str(Path(artifact_root) / "verification_ledger.json"),
    )
    result = server.call_tool(
        "omc_simulate_model",
        {
            "model_text": str(candidate_text),
            "model_name": task_ctx["model_name"],
            "source_file_name": task_ctx["source_file_name"],
            "source_library_path": task_ctx["source_library_path"],
            "source_package_name": task_ctx["source_package_name"],
            "source_library_model_path": task_ctx["source_library_model_path"],
            "source_qualified_model_name": task_ctx["source_qualified_model_name"],
            "extra_model_loads": list(task_ctx.get("extra_model_loads") or []),
        },
    )
    return result


def _tool_call_count(ledger_path: str) -> int:
    payload = _load_json(ledger_path)
    return int(payload.get("tool_call_count") or 0)


def run_external_agent_live(
    *,
    provider_name: str,
    arm_id: str,
    taskset_path: str = DEFAULT_TASKSET,
    out_dir: str = DEFAULT_OUT_DIR,
    budget_path: str = DEFAULT_BUDGET,
    model_id: str = "",
    model_id_resolvable: bool = False,
    docker_image: str = DEFAULT_DOCKER_IMAGE,
    max_tasks: int = 0,
) -> dict:
    tasks = _load_tasks(taskset_path)
    if max_tasks > 0:
        tasks = tasks[:max_tasks]
    budget = _budget_from_seal(budget_path)
    out_root = Path(out_dir)
    schema_path = out_root / "response_schema.json"
    _write_json(schema_path, _output_schema())

    raw_records: list[dict] = []
    provider = _norm(provider_name).lower()
    if provider not in SUPPORTED_EXTERNAL_PROVIDERS:
        raise ValueError(f"unsupported_provider:{provider_name}")

    for task in tasks:
        task_ctx = _task_context(task)
        task_root = out_root / "tasks" / task_ctx["task_id"]
        ledger_path = task_root / "mcp_ledger.json"
        server_cmd = _server_command(
            docker_image=docker_image,
            artifact_root=str(task_root / "mcp_artifacts"),
            ledger_path=str(ledger_path),
        )
        prompt = _arm_prompt(task_ctx, arm_id=arm_id, budget=budget)
        prompt_path = task_root / "prompt.txt"
        _write_text(prompt_path, prompt)
        task_result: dict = {
            "task_id": task_ctx["task_id"],
            "success": False,
            "task_status": "FAIL",
            "infra_failure": False,
            "infra_failure_reason": "",
            "budget_exhausted": False,
            "agent_rounds": 0,
            "omc_tool_call_count": 0,
            "wall_clock_sec": 0.0,
            "output_text": "",
        }
        started = time.time()
        provider_output = ""
        provider_err = ""
        parsed_payload: dict = {}
        try:
            if provider == "claude":
                mcp_config_path = task_root / "provider_mcp_config.json"
                _write_json(mcp_config_path, _provider_mcp_config(server_cmd))
                cmd = _build_provider_inline_mcp_command(
                    provider_name=provider,
                    prompt=prompt,
                    mcp_config_path=str(mcp_config_path.resolve()),
                    output_schema_path=str(schema_path.resolve()),
                    model_id=model_id,
                )
                proc = _run_subprocess(cmd, timeout_sec=int(budget.get("max_wall_clock_sec") or 90) + 90)
                provider_output = str(proc.stdout or "")
                provider_err = str(proc.stderr or "")
                _write_text(task_root / "provider_stdout.txt", provider_output)
                _write_text(task_root / "provider_stderr.txt", provider_err)
                if proc.returncode != 0:
                    task_result["infra_failure"] = True
                    task_result["infra_failure_reason"] = _task_infra_reason(provider_output + "\n" + provider_err)
                parsed_payload = _extract_json_payload(provider_output)
            else:
                server_name = f"gateforge_omc_{uuid.uuid4().hex[:8]}"
                add_proc = _run_subprocess(
                    _build_provider_registered_server_add_command(
                        provider_name=provider,
                        server_name=server_name,
                        server_cmd=server_cmd,
                    ),
                    timeout_sec=30,
                )
                if add_proc.returncode != 0:
                    provider_output = str(add_proc.stdout or "")
                    provider_err = str(add_proc.stderr or "")
                    task_result["infra_failure"] = True
                    task_result["infra_failure_reason"] = "mcp_config_failed"
                else:
                    last_message_path = task_root / "provider_last_message.json"
                    # Some provider CLIs register MCP servers globally. Add a server-name
                    # hint so the run uses the task-specific server instead of a stale one.
                    provider_prompt = _append_provider_server_hint(
                        provider_name=provider,
                        prompt=prompt,
                        server_name=server_name,
                    )
                    exec_proc = _run_subprocess(
                        _build_provider_registered_server_exec_command(
                            provider_name=provider,
                            prompt=provider_prompt,
                            output_schema_path=str(schema_path),
                            last_message_path=str(last_message_path),
                            model_id=model_id,
                            cwd=str(Path.cwd()),
                        ),
                        timeout_sec=int(budget.get("max_wall_clock_sec") or 90) + 90,
                    )
                    provider_output = str(exec_proc.stdout or "")
                    provider_err = str(exec_proc.stderr or "")
                    _write_text(task_root / "provider_stdout.txt", provider_output)
                    _write_text(task_root / "provider_stderr.txt", provider_err)
                    if exec_proc.returncode != 0:
                        task_result["infra_failure"] = True
                        task_result["infra_failure_reason"] = _task_infra_reason(provider_output + "\n" + provider_err)
                    if last_message_path.exists():
                        parsed_payload = _extract_json_payload(last_message_path.read_text(encoding="utf-8"))
                    _run_subprocess(
                        _build_provider_registered_server_remove_command(
                            provider_name=provider,
                            server_name=server_name,
                        ),
                        timeout_sec=30,
                    )
        except subprocess.TimeoutExpired:
            task_result["infra_failure"] = True
            task_result["infra_failure_reason"] = "provider_timeout"

        task_result["wall_clock_sec"] = round(time.time() - started, 2)
        task_result["output_text"] = provider_output[-2000:] if provider_output else provider_err[-2000:]
        task_result["omc_tool_call_count"] = _tool_call_count(str(ledger_path))
        task_result["agent_rounds"] = int(parsed_payload.get("rounds_used_estimate") or 0)
        task_result["budget_exhausted"] = bool(parsed_payload.get("budget_exhausted")) or (
            int(task_result["omc_tool_call_count"]) >= int(budget.get("max_omc_tool_calls") or 0) > 0
        )
        if int(task_result["omc_tool_call_count"]) <= 0:
            task_result["task_status"] = "FAIL"
            task_result["success"] = False
            task_result["output_text"] = (str(task_result["output_text"] or "") + "\nshared_tool_plane_unused").strip()
            raw_records.append(task_result)
            continue

        if not task_result["infra_failure"]:
            candidate_text = _norm(parsed_payload.get("patched_model_text")) or task_ctx["model_text"]
            verification = _verify_candidate(
                task_ctx=task_ctx,
                candidate_text=candidate_text,
                docker_image=docker_image,
                artifact_root=str(task_root),
            )
            passed = bool(verification.get("ok"))
            task_result["success"] = passed
            if passed:
                task_result["task_status"] = "PASS"
            elif task_result["budget_exhausted"] or _norm(parsed_payload.get("task_status")) == "BUDGET_EXHAUSTED":
                task_result["task_status"] = "BUDGET_EXHAUSTED"
            else:
                task_result["task_status"] = "FAIL"
            task_result["verification"] = verification
            task_result["repair_rationale"] = _norm(parsed_payload.get("repair_rationale"))
        raw_records.append(task_result)

    raw_bundle = {
        "arm_id": str(arm_id),
        "provider_name": provider,
        "model_id": _norm(model_id) or f"{provider}_default",
        "model_id_resolvable": bool(model_id_resolvable),
        "access_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "prompt_id": str(arm_id),
        "records": raw_records,
    }
    _write_json(out_root / "raw_bundle.json", raw_bundle)
    normalized = normalize_external_agent_run(raw_bundle, source_path=str((out_root / "raw_bundle.json").resolve()))
    _write_json(out_root / "normalized_bundle.json", normalized)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "provider_name": provider,
        "arm_id": str(arm_id),
        "task_count": len(raw_records),
        "infra_failure_count": len([row for row in raw_records if bool(row.get("infra_failure"))]),
        "normalized_bundle_path": str((out_root / "normalized_bundle.json").resolve()),
    }
    _write_json(out_root / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one external-agent Track C arm on the v0.3.1 holdout slice.")
    parser.add_argument("--provider", choices=list(SUPPORTED_EXTERNAL_PROVIDERS), required=True)
    parser.add_argument("--arm-id", choices=["arm1_general_agent", "arm2_frozen_structured_prompt"], required=True)
    parser.add_argument("--taskset", default=DEFAULT_TASKSET)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--budget-path", default=DEFAULT_BUDGET)
    parser.add_argument("--model-id", default="")
    parser.add_argument("--model-id-resolvable", action="store_true")
    parser.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    parser.add_argument("--max-tasks", type=int, default=0)
    args = parser.parse_args()
    payload = run_external_agent_live(
        provider_name=str(args.provider),
        arm_id=str(args.arm_id),
        taskset_path=str(args.taskset),
        out_dir=str(args.out_dir),
        budget_path=str(args.budget_path),
        model_id=str(args.model_id),
        model_id_resolvable=bool(args.model_id_resolvable),
        docker_image=str(args.docker_image),
        max_tasks=int(args.max_tasks),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": int(payload.get("task_count") or 0)}))


if __name__ == "__main__":
    main()
