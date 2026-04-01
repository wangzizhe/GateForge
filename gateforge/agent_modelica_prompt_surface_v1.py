from __future__ import annotations

import json


SCHEMA_VERSION = "agent_modelica_prompt_surface_v1"


def build_external_agent_probe_prompt(*, tool_name: str) -> str:
    return "\n".join(
        [
            "Use the shared OpenModelica MCP tool plane.",
            f"Call `{tool_name}` exactly once.",
            "Do not use shell, file editing, or any non-MCP path.",
            "After the MCP call, return only JSON matching the required schema.",
            f"Set `tool_name` to `{tool_name}` and `tool_used` to true only if you actually called it.",
        ]
    )


def build_external_agent_repair_prompt(*, task_ctx: dict, arm_id: str, budget: dict) -> str:
    budget_lines = [
        f"- max_agent_rounds: {int(budget.get('max_agent_rounds') or 0)}",
        f"- max_omc_tool_calls: {int(budget.get('max_omc_tool_calls') or 0)}",
        f"- max_wall_clock_sec: {int(budget.get('max_wall_clock_sec') or 0)}",
    ]
    task_lines = [
        f"- task_id: {task_ctx['task_id']}",
        f"- failure_type: {task_ctx['failure_type']}",
        f"- expected_stage: {task_ctx['expected_stage']}",
        f"- model_name: {task_ctx['model_name']}",
        f"- source_library_path: {task_ctx['source_library_path'] or 'none'}",
        f"- source_package_name: {task_ctx['source_package_name'] or 'none'}",
        f"- source_library_model_path: {task_ctx['source_library_model_path'] or 'none'}",
        f"- source_qualified_model_name: {task_ctx['source_qualified_model_name'] or 'none'}",
        f"- extra_model_loads: {json.dumps(task_ctx['extra_model_loads'])}",
    ]
    prompt_lines = [
        "You are repairing one broken Modelica model.",
        "You may only use the provided OpenModelica MCP tools as your diagnostic oracle.",
        "Do not rely on shell commands, local file editing, or any non-MCP diagnostic path.",
        "You must call at least one OpenModelica MCP tool before returning a final answer. A zero-tool final answer is invalid.",
        "On every OMC tool call, pass the full current candidate model in the `model_text` field.",
        "Keep the library-context fields unchanged across calls when they are provided.",
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
        "Library-context fields to preserve on every OMC tool call when they are not `none`:",
        "- `source_library_path`",
        "- `source_package_name`",
        "- `source_library_model_path`",
        "- `source_qualified_model_name`",
    ]
    if arm_id == "arm2_frozen_structured_prompt":
        prompt_lines += [
            "",
            "Work in short iterations:",
            "1. Call `omc_check_model` or `omc_simulate_model` on the current candidate text.",
            "2. Apply one repair hypothesis.",
            "3. Re-check before making another change.",
            "4. Stop when the model passes or the budget is exhausted.",
        ]
    prompt_lines += [
        "",
        "Before returning, you must have used `omc_check_model` or `omc_simulate_model` at least once on your final or near-final candidate.",
        "Return only JSON matching the required schema.",
        "If you cannot repair the model within budget, return the best candidate text you found and set `task_status` to `BUDGET_EXHAUSTED` or `FAIL`.",
    ]
    return "\n".join(prompt_lines)


def build_planner_prompt_surface(**kwargs) -> tuple[str, dict]:
    from .agent_modelica_l2_plan_replan_engine_v1 import (
        build_source_blind_multistep_planner_prompt,
    )

    return build_source_blind_multistep_planner_prompt(**kwargs)


def build_branch_switch_replan_prompt(*, task_ctx: dict, replan_ctx: dict, budget: dict | None = None) -> str:
    branch_rows = replan_ctx.get("candidate_branches") if isinstance(replan_ctx.get("candidate_branches"), list) else []
    prompt_lines = [
        "You are handling one narrow GateForge replan case.",
        "This is not a general repair task. Focus only on branch switch after stalled progress.",
        "",
        "Task Context:",
        f"- task_id: {task_ctx.get('task_id')}",
        f"- failure_type: {task_ctx.get('failure_type')}",
        f"- expected_stage: {task_ctx.get('expected_stage')}",
        f"- model_name: {task_ctx.get('model_name')}",
        "",
        "Structured Replan Context:",
        f"- previous_successful_action: {replan_ctx.get('previous_successful_action')}",
        f"- stall_signal: {replan_ctx.get('stall_signal')}",
        f"- current_branch: {replan_ctx.get('current_branch')}",
        f"- replan_count: {replan_ctx.get('replan_count')}",
        f"- remaining_replan_budget: {replan_ctx.get('remaining_replan_budget')}",
        "- candidate_branches_json:",
        json.dumps(branch_rows, indent=2),
    ]
    if isinstance(budget, dict) and budget:
        prompt_lines += [
            "",
            "Budget:",
            f"- max_replan_rounds: {int(budget.get('max_replan_rounds') or 0)}",
            f"- max_followup_actions: {int(budget.get('max_followup_actions') or 0)}",
        ]
    prompt_lines += [
        "",
        "Output requirements:",
        "- Decide whether to continue the current branch or switch to one explicit candidate branch.",
        "- Do not invent new branch ids outside `candidate_branches_json`.",
        "- The chosen branch set must be expressed through structured fields, not free-form branch text only.",
        "- Return a structured decision payload only.",
    ]
    return "\n".join(prompt_lines)
