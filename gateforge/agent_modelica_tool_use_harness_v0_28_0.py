from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_l2_plan_replan_engine_v1 import resolve_llm_provider
from .agent_modelica_observation_contract_v0_26_1 import build_observation_event, validate_observation_event
from .agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)
from .llm_provider_adapter import (
    LLMProviderAdapter,
    LLMProviderConfig,
    ToolResponse,
    resolve_provider_adapter,
)
from .agent_modelica_structural_tools_v0_28_1 import (
    dispatch_structural_tool,
    get_structural_tool_defs,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "tool_use_harness_v0_28_0"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "check_model",
        "description": (
            "Run OMC checkModel on the provided Modelica model text and return raw compiler output. "
            "Returns check results, equation counts, and any errors."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {
                    "type": "string",
                    "description": "Complete Modelica model source code to check.",
                },
            },
            "required": ["model_text"],
        },
    },
    {
        "name": "simulate_model",
        "description": (
            "Run OMC simulate on the provided Modelica model text and return simulation output. "
            "Runs checkModel first, then simulate with given stopTime and intervals."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {
                    "type": "string",
                    "description": "Complete Modelica model source code to simulate.",
                },
                "stop_time": {
                    "type": "number",
                    "description": "Simulation stop time in seconds. Default: 0.05",
                },
                "intervals": {
                    "type": "integer",
                    "description": "Number of simulation intervals. Default: 100",
                },
            },
            "required": ["model_text"],
        },
    },
    {
        "name": "submit_final",
        "description": (
            "Submit the final repaired model for evaluation. "
            "Call this when you believe the model is correct. "
            "The submitted model will be evaluated with checkModel and simulate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {
                    "type": "string",
                    "description": "The final complete Modelica model source code.",
                },
            },
            "required": ["model_text"],
        },
    },
]

# Merge structural tools into the tool set
TOOL_DEFS = TOOL_DEFS + get_structural_tool_defs()


def _strip_ws(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _extract_model_name(text: str) -> str:
    m = re.search(r"^\s*model\s+(\w+)", text, re.MULTILINE)
    if m:
        return m.group(1)
    m = re.search(r"^\s*block\s+(\w+)", text, re.MULTILINE)
    if m:
        return m.group(1)
    return "model"


def dispatch_tool(name: str, arguments: dict) -> str:
    model_text = str(arguments.get("model_text") or "")
    model_name = _extract_model_name(model_text) or "model"
    if name in ("check_model", "simulate_model", "submit_final"):
        if not model_text.strip():
            return json.dumps({"error": "model_text required"})
    if name == "check_model":
        _, output, check_ok, _sim = _run_omc(model_text, model_name)
        return str(output or "")
    if name == "simulate_model":
        stop_time = float(arguments.get("stop_time") or 0.05)
        intervals = max(1, int(arguments.get("intervals") or 100))
        _, output, _check_ok, _sim = _run_omc(model_text, model_name, stop_time=stop_time, intervals=intervals)
        return str(output or "")
    if name == "submit_final":
        return json.dumps({"status": "submitted", "model_name": model_name})
    return dispatch_structural_tool(name, arguments)


def _run_omc(
    model_text: str,
    model_name: str,
    stop_time: float = 0.05,
    intervals: int = 5,
) -> tuple[int | None, str, bool, bool]:
    with temporary_workspace("gf_v0280_tool_") as ws:
        workspace = Path(ws)
        layout = prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=Path(f"{model_name}.mo"),
            primary_model_name=model_name,
            source_library_path="",
            source_package_name="",
            source_library_model_path="",
            source_qualified_model_name=model_name,
        )
        layout.model_write_path.write_text(model_text, encoding="utf-8")
        return run_check_and_simulate(
            workspace=workspace,
            model_load_files=list(layout.model_load_files),
            model_name=layout.model_identifier,
            timeout_sec=180,
            backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
            stop_time=float(stop_time),
            intervals=int(intervals),
            extra_model_loads=[],
        )


def run_tool_use_case(
    case: dict[str, Any],
    *,
    max_steps: int,
    max_token_budget: int,
    planner_backend: str = "auto",
) -> dict[str, Any]:
    current_text = str(case["model_text"])
    model_name = str(case["model_name"])
    case_id = str(case["case_id"])
    workflow_goal = str(case.get("workflow_goal") or "")
    adapter, config = resolve_provider_adapter(planner_backend)
    provider = config.provider_name
    if provider == "rule":
        return _fail_result(case_id, model_name, "rule_backend_selected")

    system_prompt = (
        "You are fixing a Modelica model. You can use tools to check and simulate the model.\n"
        "Use check_model to see current compiler output.\n"
        "Use simulate_model to run a simulation.\n"
        "When the model is correct, call submit_final.\n"
        "Keep edits minimal and compile-oriented.\n"
        "Return patched_model_text through submit_final only.\n"
    )
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"Task: {workflow_goal}\n\n"
            f"Model name: {model_name}\n\n"
            f"Current model:\n-----BEGIN_MODEL-----\n{current_text}\n-----END_MODEL-----\n"
        )},
    ]
    steps: list[dict] = []
    token_used = 0
    final_verdict = "FAILED"
    final_model = current_text
    submitted = False
    provider_error = ""

    for step_idx in range(1, max(1, int(max_steps)) + 1):
        resp, err = adapter.send_tool_request(messages, TOOL_DEFS, config)
        if err:
            provider_error = err
            steps.append({"step": step_idx, "error": err})
            break
        if resp is None:
            steps.append({"step": step_idx, "error": "null_response"})
            break
        token_used += resp.usage.get("total_tokens", 0)
        step_record: dict = {
            "step": step_idx,
            "text": resp.text,
            "tool_calls": [{"name": tc.name, "arguments": tc.arguments} for tc in resp.tool_calls],
            "token_used": token_used,
        }
        if resp.tool_calls:
            assistant_msg: dict = {"role": "assistant", "content": resp.text or None}
            reasoning = resp.usage.get("_reasoning_content", "")
            if reasoning:
                assistant_msg["reasoning_content"] = reasoning
            tc_list = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in resp.tool_calls
            ]
            assistant_msg["tool_calls"] = tc_list
            messages.append(assistant_msg)
            tool_results = []
            should_break = False
            for tc in resp.tool_calls:
                args = dict(tc.arguments)
                if not args.get("model_text", "").strip():
                    args["model_text"] = current_text
                result = dispatch_tool(tc.name, args)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                tool_results.append({"name": tc.name, "result": result[:500]})
                if tc.name == "submit_final":
                    submitted = True
                    final_model = str(tc.arguments.get("model_text") or current_text)
                    should_break = True
            step_record["tool_results"] = tool_results
            if should_break:
                break
        else:
            messages.append({"role": "assistant", "content": resp.text})
        steps.append(step_record)
        if submitted:
            break
        if token_used >= max_token_budget:
            break

    if submitted:
        final_model_name = _extract_model_name(final_model) or model_name
        _, output, check_ok, simulate_ok = _run_omc(final_model, final_model_name)
        final_verdict = "PASS" if (check_ok and simulate_ok) else "FAILED"
        steps.append({"step": "final_eval", "check_ok": check_ok, "simulate_ok": simulate_ok, "omc_output": str(output or "")[:2000]})

    result = {
        "case_id": case_id,
        "model_name": model_name,
        "provider": provider,
        "run_mode": "tool_use",
        "final_verdict": final_verdict,
        "submitted": submitted,
        "step_count": len(steps),
        "token_used": token_used,
        "provider_error": provider_error,
        "steps": steps,
        "final_model_text": final_model,
    }
    return result


def _fail_result(case_id: str, model_name: str, error: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "model_name": model_name,
        "provider": "",
        "run_mode": "tool_use",
        "final_verdict": "FAILED",
        "submitted": False,
        "step_count": 0,
        "token_used": 0,
        "provider_error": error,
        "steps": [],
        "final_model_text": "",
    }


def run_tool_use_baseline(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    cases: list[dict[str, Any]],
    limit: int = 1,
    max_steps: int = 10,
    max_token_budget: int = 32000,
    planner_backend: str = "auto",
) -> dict[str, Any]:
    selected = list(cases)[:max(0, int(limit))]
    results = [
        run_tool_use_case(case, max_steps=max_steps, max_token_budget=max_token_budget, planner_backend=planner_backend)
        for case in selected
    ]
    total = len(results)
    pass_count = sum(1 for r in results if r.get("final_verdict") == "PASS")
    summary = {
        "version": "v0.28.0",
        "status": "PASS" if total else "REVIEW",
        "analysis_scope": "tool_use_harness_smoke",
        "run_mode": "tool_use",
        "case_count": total,
        "pass_count": pass_count,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "comparative_claim_made": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": "tool_use_harness_artifact_ready" if total else "tool_use_harness_needs_cases",
    }
    write_outputs(out_dir=out_dir, summary=summary, results=results)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], results: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for row in results:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
