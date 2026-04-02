from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .agent_modelica_external_agent_live_runner_v0_3_1 import (
    DEFAULT_BUDGET,
    DEFAULT_DOCKER_IMAGE,
    DEFAULT_TASKSET,
    _budget_from_seal,
    _extract_json_payload,
    _load_tasks,
    _output_schema,
    _task_context,
    _verify_candidate,
)
from .agent_modelica_external_agent_runner_v1 import normalize_external_agent_run
from .agent_modelica_omc_mcp_server_v1 import TOOL_NAMES, OmcMcpServer, _tool_defs
from .llm_provider_adapter import LLMProviderConfig, resolve_provider_adapter


SCHEMA_VERSION = "agent_modelica_api_direct_generic_runner_v0_3_2"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_api_direct_generic_runner_v0_3_2"


def _norm(value: object) -> str:
    return str(value or "").strip()


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_openai_function_tools() -> list[dict]:
    tools: list[dict] = []
    for row in _tool_defs():
        if not isinstance(row, dict):
            continue
        parameters = dict(row.get("inputSchema") or {"type": "object", "properties": {}})
        if parameters.get("type") == "object" and "additionalProperties" not in parameters:
            parameters["additionalProperties"] = False
        tools.append(
            {
                "type": "function",
                "name": str(row.get("name") or ""),
                "description": str(row.get("description") or ""),
                "parameters": parameters,
                "strict": True,
            }
        )
    return tools


def build_anthropic_tools() -> list[dict]:
    tools: list[dict] = []
    for row in _tool_defs():
        if not isinstance(row, dict):
            continue
        parameters = dict(row.get("inputSchema") or {"type": "object", "properties": {}})
        tools.append(
            {
                "name": str(row.get("name") or ""),
                "description": str(row.get("description") or ""),
                "input_schema": parameters,
            }
        )
    return tools


def build_api_direct_task_prompt(*, task_ctx: dict, budget: dict, tool_defs: list[dict]) -> str:
    budget_lines = [
        f"- max_agent_rounds: {int(budget.get('max_agent_rounds') or 0)}",
        f"- max_omc_tool_calls: {int(budget.get('max_omc_tool_calls') or 0)}",
        f"- max_wall_clock_sec: {int(budget.get('max_wall_clock_sec') or 0)}",
    ]
    tool_names = [str(row.get("name") or "") for row in tool_defs if isinstance(row, dict) and str(row.get("name") or "").strip()]
    task_lines = [
        f"- task_id: {task_ctx['task_id']}",
        f"- failure_type: {task_ctx['failure_type']}",
        f"- expected_stage: {task_ctx['expected_stage']}",
        f"- model_name: {task_ctx['model_name']}",
        f"- source_package_name: {task_ctx['source_package_name'] or 'none'}",
        f"- extra_model_loads: {json.dumps(task_ctx['extra_model_loads'])}",
        f"- available_omc_tools: {json.dumps(tool_names)}",
    ]
    checklist_lines = [
        "- full task context is provided below, including the broken Modelica code",
        "- the available OMC tools are listed explicitly",
        "- multi-round tool use is allowed within budget",
        "- you should use the tools as your diagnostic oracle, not rely on unsupported hidden context",
    ]
    return "\n".join(
        [
            "You are repairing one broken Modelica model.",
            "Use the provided OMC function tools as the executable diagnostic oracle.",
            "You may take multiple rounds of tool use within the stated budget.",
            "Return only JSON matching the required final schema once you are ready to stop.",
            "",
            "Fairness checklist:",
            *checklist_lines,
            "",
            "Budget:",
            *budget_lines,
            "",
            "Task Context:",
            *task_lines,
            "",
            "Broken Modelica model text:",
            "```modelica",
            task_ctx["model_text"],
            "```",
            "",
            "Work loop:",
            "1. Inspect the current candidate with `omc_check_model` or `omc_simulate_model`.",
            "2. Update your candidate repair hypothesis.",
            "3. Re-check before making another change when budget allows.",
            "4. Stop when the model passes or the budget is exhausted.",
            "",
            "Final response requirements:",
            "- include task_status, budget_exhausted, rounds_used_estimate, patched_model_text, repair_rationale",
            "- do not omit patched_model_text even if you keep the original text",
        ]
    )


@dataclass
class APIDirectToolCall:
    call_id: str
    name: str
    arguments: dict


@dataclass
class APIDirectTurnResult:
    output_items: list[dict]
    tool_calls: list[APIDirectToolCall]
    output_text: str
    response_id: str = ""


class APIDirectProviderClient(Protocol):
    def run_turn(
        self,
        *,
        input_items: list[object],
        tools: list[dict],
        model_id: str,
        final_schema: dict,
    ) -> APIDirectTurnResult:
        ...


class OpenAIResponsesToolClient:
    def __init__(self, *, config: LLMProviderConfig) -> None:
        self.config = config

    def _post(self, payload: dict) -> dict:
        if not _norm(self.config.api_key):
            raise ValueError("openai_api_key_missing")
        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=float(self.config.timeout_sec or 120.0)) as resp:
                body = resp.read().decode("utf-8")
        except TimeoutError as exc:
            raise RuntimeError("openai_request_timeout") from exc
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"openai_http_error:{int(exc.code)}:{body[:180]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"openai_url_error:{exc.reason}") from exc
        payload = json.loads(body)
        return payload if isinstance(payload, dict) else {}

    def run_turn(
        self,
        *,
        input_items: list[object],
        tools: list[dict],
        model_id: str,
        final_schema: dict,
    ) -> APIDirectTurnResult:
        payload = self._post(
            {
                "model": str(model_id),
                "input": list(input_items),
                "tools": list(tools),
                "text": {"format": {"type": "json_schema", "name": "gateforge_final_output", "schema": final_schema}},
            }
        )
        output_items = [row for row in (payload.get("output") or []) if isinstance(row, dict)]
        tool_calls: list[APIDirectToolCall] = []
        for row in output_items:
            if str(row.get("type") or "") != "function_call":
                continue
            arguments_text = str(row.get("arguments") or "{}")
            try:
                arguments = json.loads(arguments_text)
            except Exception:
                arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            tool_calls.append(
                APIDirectToolCall(
                    call_id=str(row.get("call_id") or row.get("id") or ""),
                    name=str(row.get("name") or ""),
                    arguments=arguments,
                )
            )
        output_text = ""
        if isinstance(payload.get("output_text"), str):
            output_text = str(payload.get("output_text") or "")
        if not output_text:
            texts: list[str] = []
            for row in output_items:
                content = row.get("content") if isinstance(row.get("content"), list) else []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    text = str(part.get("text") or part.get("value") or "").strip()
                    if text:
                        texts.append(text)
            output_text = "\n".join(texts).strip()
        return APIDirectTurnResult(
            output_items=output_items,
            tool_calls=tool_calls,
            output_text=output_text,
            response_id=str(payload.get("id") or ""),
        )


class AnthropicMessagesToolClient:
    def __init__(self, *, config: LLMProviderConfig) -> None:
        self.config = config

    def _post(self, payload: dict) -> dict:
        if not _norm(self.config.api_key):
            raise ValueError("anthropic_api_key_missing")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": f"{self.config.api_key}",
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=float(self.config.timeout_sec or 120.0)) as resp:
                body = resp.read().decode("utf-8")
        except TimeoutError as exc:
            raise RuntimeError("anthropic_request_timeout") from exc
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"anthropic_http_error:{int(exc.code)}:{body[:180]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"anthropic_url_error:{exc.reason}") from exc
        payload = json.loads(body)
        return payload if isinstance(payload, dict) else {}

    def _messages_from_items(self, input_items: list[object]) -> list[dict]:
        messages: list[dict] = []
        for item in input_items:
            if isinstance(item, str):
                if messages and messages[-1]["role"] == "user":
                    messages[-1]["content"].append({"type": "text", "text": item})
                else:
                    messages.append({"role": "user", "content": [{"type": "text", "text": item}]})
                continue
            if not isinstance(item, dict):
                continue
            item_type = _norm(item.get("type"))
            if item_type == "function_call_output":
                if not messages or messages[-1]["role"] != "user":
                    messages.append({"role": "user", "content": []})
                messages[-1]["content"].append(
                    {
                        "type": "tool_result",
                        "tool_use_id": _norm(item.get("call_id")),
                        "content": _norm(item.get("output")),
                    }
                )
                continue
            if item_type in {"text", "tool_use"}:
                if not messages or messages[-1]["role"] != "assistant":
                    messages.append({"role": "assistant", "content": []})
                block = dict(item)
                messages[-1]["content"].append(block)
        return [row for row in messages if row.get("content")]

    def run_turn(
        self,
        *,
        input_items: list[object],
        tools: list[dict],
        model_id: str,
        final_schema: dict,
    ) -> APIDirectTurnResult:
        prompt_suffix = (
            "\nReturn only the final JSON object when you stop. "
            f"The JSON schema is: {json.dumps(final_schema, sort_keys=True)}"
        )
        messages = self._messages_from_items(input_items)
        if messages and messages[-1]["role"] == "user" and messages[-1]["content"]:
            last = messages[-1]["content"][-1]
            if isinstance(last, dict) and _norm(last.get("type")) == "text":
                last["text"] = f"{_norm(last.get('text'))}{prompt_suffix}"
        payload = self._post(
            {
                "model": str(model_id),
                "max_tokens": 2048,
                "messages": messages,
                "tools": list(tools),
                "temperature": 0.0,
            }
        )
        content = [row for row in (payload.get("content") or []) if isinstance(row, dict)]
        tool_calls: list[APIDirectToolCall] = []
        text_parts: list[str] = []
        output_items: list[dict] = []
        for row in content:
            row_type = _norm(row.get("type"))
            if row_type == "tool_use":
                call_id = _norm(row.get("id"))
                tool_calls.append(
                    APIDirectToolCall(
                        call_id=call_id,
                        name=_norm(row.get("name")),
                        arguments=dict(row.get("input") or {}),
                    )
                )
                output_items.append(
                    {
                        "type": "tool_use",
                        "id": call_id,
                        "name": _norm(row.get("name")),
                        "input": dict(row.get("input") or {}),
                    }
                )
            elif row_type == "text":
                text = _norm(row.get("text"))
                if text:
                    text_parts.append(text)
                output_items.append({"type": "text", "text": text})
        return APIDirectTurnResult(
            output_items=output_items,
            tool_calls=tool_calls,
            output_text="\n".join([part for part in text_parts if part]).strip(),
            response_id=_norm(payload.get("id")),
        )


class ToolExecutor(Protocol):
    def call_tool(self, tool_name: str, arguments: dict | None = None) -> dict:
        ...


def _tool_output_item(*, call_id: str, result: dict) -> dict:
    return {
        "type": "function_call_output",
        "call_id": str(call_id),
        "output": json.dumps(result),
    }


def run_api_direct_task(
    *,
    task_ctx: dict,
    budget: dict,
    client: APIDirectProviderClient,
    tool_executor: ToolExecutor,
    tool_defs: list[dict],
    model_id: str,
    docker_image: str,
    artifact_root: str,
) -> dict:
    prompt = build_api_direct_task_prompt(task_ctx=task_ctx, budget=budget, tool_defs=tool_defs)
    input_items: list[object] = [prompt]
    transcript: list[object] = []
    final_schema = _output_schema()
    max_rounds = max(1, int(budget.get("max_agent_rounds") or 1))
    max_tool_calls = max(0, int(budget.get("max_omc_tool_calls") or 0))
    agent_rounds = 0
    omc_tool_call_count = 0
    budget_exhausted = False
    final_payload: dict = {}
    last_output_text = ""

    for round_idx in range(max_rounds):
        agent_rounds = round_idx + 1
        turn = client.run_turn(
            input_items=input_items,
            tools=tool_defs,
            model_id=model_id,
            final_schema=final_schema,
        )
        transcript.extend(turn.output_items)
        input_items.extend(turn.output_items)
        last_output_text = str(turn.output_text or "")

        executed_tool = False
        for tool_call in turn.tool_calls:
            if tool_call.name not in TOOL_NAMES:
                continue
            if max_tool_calls > 0 and omc_tool_call_count >= max_tool_calls:
                budget_exhausted = True
                break
            result = tool_executor.call_tool(tool_call.name, dict(tool_call.arguments))
            omc_tool_call_count += 1
            output_item = _tool_output_item(call_id=tool_call.call_id, result=result)
            transcript.append(output_item)
            input_items.append(output_item)
            executed_tool = True
        if budget_exhausted:
            break
        if executed_tool:
            continue

        final_payload = _extract_json_payload(last_output_text)
        if final_payload:
            break

    record = {
        "task_id": task_ctx["task_id"],
        "success": False,
        "task_status": "FAIL",
        "infra_failure": False,
        "infra_failure_reason": "",
        "budget_exhausted": budget_exhausted,
        "agent_rounds": agent_rounds,
        "omc_tool_call_count": omc_tool_call_count,
        "tool_calls": [
            {
                "type": "function_call_output" if isinstance(row, dict) and str(row.get("type") or "") == "function_call_output" else str(row.get("type") or ""),
                "name": str(row.get("name") or ""),
                "call_id": str(row.get("call_id") or ""),
            }
            for row in transcript
            if isinstance(row, dict)
        ],
        "output_text": last_output_text[-2000:],
        "prompt_text": prompt,
    }
    if omc_tool_call_count <= 0:
        record["output_text"] = (str(record["output_text"] or "") + "\nshared_tool_plane_unused").strip()
        return record

    candidate_text = _norm(final_payload.get("patched_model_text")) or task_ctx["model_text"]
    verification = _verify_candidate(
        task_ctx=task_ctx,
        candidate_text=candidate_text,
        docker_image=docker_image,
        artifact_root=str(artifact_root),
    )
    passed = bool(verification.get("ok"))
    record["success"] = passed
    if passed:
        record["task_status"] = "PASS"
    elif budget_exhausted or _norm(final_payload.get("task_status")) == "BUDGET_EXHAUSTED":
        record["task_status"] = "BUDGET_EXHAUSTED"
        record["budget_exhausted"] = True
    else:
        record["task_status"] = "FAIL"
    record["verification"] = verification
    record["repair_rationale"] = _norm(final_payload.get("repair_rationale"))
    return record


def _build_client(*, provider_family: str, model_id: str) -> tuple[APIDirectProviderClient, str, str]:
    adapter, config = resolve_provider_adapter(provider_family)
    provider_name = str(config.provider_name or "").strip().lower()
    if provider_name not in {"openai", "anthropic"}:
        raise ValueError(f"unsupported_api_direct_provider:{provider_name}")
    resolved_model = _norm(model_id) or _norm(config.model)
    if not resolved_model:
        raise ValueError("model_id_required_for_api_direct_runner")
    if provider_name == "openai":
        return OpenAIResponsesToolClient(config=config), provider_name, resolved_model
    return AnthropicMessagesToolClient(config=config), provider_name, resolved_model


def run_api_direct_generic_runner(
    *,
    provider_family: str,
    arm_id: str,
    taskset_path: str = DEFAULT_TASKSET,
    out_dir: str = DEFAULT_OUT_DIR,
    budget_path: str = DEFAULT_BUDGET,
    model_id: str = "",
    docker_image: str = DEFAULT_DOCKER_IMAGE,
    max_tasks: int = 0,
) -> dict:
    tasks = _load_tasks(taskset_path)
    if max_tasks > 0:
        tasks = tasks[:max_tasks]
    budget = _budget_from_seal(budget_path)
    client, provider_name, resolved_model_id = _build_client(provider_family=provider_family, model_id=model_id)
    tool_defs = build_openai_function_tools() if provider_name == "openai" else build_anthropic_tools()
    out_root = Path(out_dir)

    raw_records: list[dict] = []
    for task in tasks:
        task_ctx = _task_context(task)
        task_root = out_root / "tasks" / task_ctx["task_id"]
        server = OmcMcpServer(
            backend="openmodelica_docker",
            docker_image=str(docker_image),
            timeout_sec=120,
            artifact_root=str(task_root / "omc_artifacts"),
            default_stop_time=1.0,
            default_intervals=500,
            ledger_path=str(task_root / "tool_ledger.json"),
        )
        started = datetime.now(timezone.utc)
        try:
            record = run_api_direct_task(
                task_ctx=task_ctx,
                budget=budget,
                client=client,
                tool_executor=server,
                tool_defs=tool_defs,
                model_id=resolved_model_id,
                docker_image=docker_image,
                artifact_root=str(task_root),
            )
        except Exception as exc:
            record = {
                "task_id": task_ctx["task_id"],
                "success": False,
                "task_status": "FAIL",
                "infra_failure": True,
                "infra_failure_reason": f"api_direct_runner_error:{type(exc).__name__}",
                "budget_exhausted": False,
                "agent_rounds": 0,
                "omc_tool_call_count": 0,
                "output_text": str(exc),
            }
        wall_clock_sec = (datetime.now(timezone.utc) - started).total_seconds()
        record["wall_clock_sec"] = round(max(0.0, wall_clock_sec), 2)
        _write_json(task_root / "task_record.json", record)
        raw_records.append(record)

    raw_bundle = {
        "arm_id": str(arm_id),
        "provider_name": f"{provider_name}_api_direct",
        "model_id": resolved_model_id,
        "model_id_resolvable": True,
        "access_timestamp_utc": _now_utc(),
        "prompt_id": "api_direct_fair_prompt_v1",
        "records": raw_records,
    }
    _write_json(out_root / "raw_bundle.json", raw_bundle)
    normalized = normalize_external_agent_run(raw_bundle, source_path=str((out_root / "raw_bundle.json").resolve()))
    _write_json(out_root / "normalized_bundle.json", normalized)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "provider_family": str(provider_family),
        "provider_name": f"{provider_name}_api_direct",
        "arm_id": str(arm_id),
        "task_count": len(raw_records),
        "infra_failure_count": len([row for row in raw_records if bool(row.get("infra_failure"))]),
        "normalized_bundle_path": str((out_root / "normalized_bundle.json").resolve()),
    }
    _write_json(out_root / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a minimal API-direct generic-agent baseline on the shared OMC tool surface.")
    parser.add_argument("--provider-family", choices=["auto", "openai", "anthropic"], default="auto")
    parser.add_argument("--arm-id", default="arm_api_direct_generic")
    parser.add_argument("--taskset", default=DEFAULT_TASKSET)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--budget-path", default=DEFAULT_BUDGET)
    parser.add_argument("--model-id", default="")
    parser.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    parser.add_argument("--max-tasks", type=int, default=0)
    args = parser.parse_args()
    payload = run_api_direct_generic_runner(
        provider_family=str(args.provider_family),
        arm_id=str(args.arm_id),
        taskset_path=str(args.taskset),
        out_dir=str(args.out_dir),
        budget_path=str(args.budget_path),
        model_id=str(args.model_id),
        docker_image=str(args.docker_image),
        max_tasks=int(args.max_tasks),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": int(payload.get("task_count") or 0)}))


if __name__ == "__main__":
    main()
