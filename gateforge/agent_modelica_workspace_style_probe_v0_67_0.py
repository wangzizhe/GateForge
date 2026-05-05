from __future__ import annotations

import json
import multiprocessing as mp
import re
from pathlib import Path
from typing import Any, Callable

from .agent_modelica_benchmark_behavioral_oracle_v0_29_3 import evaluate_benchmark_behavior
from .agent_modelica_boundary_tool_use_baseline_v0_29_2 import task_to_tool_use_case
from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json, load_jsonl
from .agent_modelica_omc_workspace_v1 import prepare_workspace_model_layout, run_check_and_simulate
from .llm_provider_adapter import resolve_provider_adapter


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASKS = REPO_ROOT / "artifacts" / "benchmark_external_bundle_v0_61_0" / "tasks.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "workspace_style_probe_v0_67_0"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"


WORKSPACE_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "list_workspace_files",
        "description": (
            "List all files in the case workspace directory. Use this to discover "
            "available models, reference files, and library definitions before writing candidates."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read the contents of any file in the workspace. Use this to inspect model "
            "definitions, connector types, and available libraries."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to workspace root."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_and_check_candidate_model",
        "description": (
            "Write a complete candidate Modelica model into the transparent case workspace "
            "and immediately run OMC checkModel AND simulate on it. Returns raw compiler output, "
            "equation balance summary, and structured diagnostics (unconstrained variables, "
            "flow sum equations, subsystem imbalance). "
            "This does not select or submit the candidate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "candidate_id": {"type": "string", "description": "Short candidate identifier."},
                "model_text": {"type": "string", "description": "Complete Modelica model source."},
                "rationale": {"type": "string", "description": "Brief reason for this candidate."},
            },
            "required": ["candidate_id", "model_text"],
        },
    },
    {
        "name": "submit_candidate_model",
        "description": (
            "Submit a previously written candidate model for final evaluation. "
            "The harness will evaluate the submitted file with checkModel and simulate; "
            "it will not choose candidates or submit automatically."
        ),
        "parameters": {
            "type": "object",
            "properties": {"candidate_id": {"type": "string"}},
            "required": ["candidate_id"],
        },
    },
    {
        "name": "update_repair_progress",
        "description": (
            "Track your repair progress with a structured task list. "
            "Use this to plan your repair strategy, mark completed analysis steps, "
            "and track which fixes have been attempted. Helps prevent thrashing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "Task description."},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "cancelled"]},
                        },
                        "required": ["content", "status"],
                    },
                },
            },
            "required": ["todos"],
        },
    },
    {
        "name": "batch_check_candidates",
        "description": (
            "Write and check multiple candidate models in one call. "
            "Use this to test several fix strategies simultaneously and compare results. "
            "Returns a comparison table showing check_ok, equation balance, and deficit for each."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "candidate_id": {"type": "string"},
                            "model_text": {"type": "string"},
                            "rationale": {"type": "string"},
                        },
                        "required": ["candidate_id", "model_text"],
                    },
                },
            },
            "required": ["candidates"],
        },
    },
]


def _safe_candidate_id(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return text[:80] or "candidate"


def _extract_model_name(text: str) -> str:
    match = re.search(r"^\s*model\s+(\w+)", text, re.MULTILINE)
    return match.group(1) if match else "model"


def _run_omc_check(
    *,
    workspace: Path,
    candidate_path: Path,
) -> tuple[str, bool, bool]:
    model_text = candidate_path.read_text(encoding="utf-8")
    model_name = _extract_model_name(model_text)
    layout = prepare_workspace_model_layout(
        workspace=workspace,
        fallback_model_path=Path(f"{model_name}.mo"),
        primary_model_name=model_name,
        source_qualified_model_name=model_name,
    )
    layout.model_write_path.write_text(model_text, encoding="utf-8")
    _, output, check_ok, simulate_ok = run_check_and_simulate(
        workspace=workspace,
        model_load_files=list(layout.model_load_files),
        model_name=layout.model_identifier,
        timeout_sec=180,
        backend="openmodelica_docker",
        docker_image=DOCKER_IMAGE,
        stop_time=0.05,
        intervals=100,
        extra_model_loads=[],
    )
    return str(output or ""), bool(check_ok), bool(simulate_ok)


def _run_omc_simulate(
    *,
    workspace: Path,
    candidate_path: Path,
    stop_time: float,
    intervals: int,
) -> str:
    model_text = candidate_path.read_text(encoding="utf-8")
    model_name = _extract_model_name(model_text)
    layout = prepare_workspace_model_layout(
        workspace=workspace,
        fallback_model_path=Path(f"{model_name}.mo"),
        primary_model_name=model_name,
        source_qualified_model_name=model_name,
    )
    layout.model_write_path.write_text(model_text, encoding="utf-8")
    _, output, _check_ok, _simulate_ok = run_check_and_simulate(
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
    return str(output or "")


def _extract_omc_diagnostics(output: str) -> dict[str, Any]:
    diag: dict[str, Any] = {}
    unconstrained: list[str] = []
    flow_sums: list[str] = []

    for line in output.splitlines():
        stripped = line.strip()
        m_uncon = re.search(r"Variable\s+(\S+)\s+does not have any remaining equation", stripped)
        if m_uncon:
            unconstrained.append(m_uncon.group(1))

        m_flow = re.search(r"Equation\s+\d+.*([\w.\[\]]+\s*\+\s*[\w.\[\]]+.*=\s*0\.0)", stripped)
        if m_flow and not m_flow.group(1).startswith("0.0"):
            flow_sums.append(m_flow.group(1).strip())

    if unconstrained:
        diag["unconstrained_variables"] = unconstrained[:10]

    if flow_sums:
        diag["flow_sum_equations"] = flow_sums[:5]

    subsystem_match = re.search(
        r"imbalanced number of equations\s*\((\d+)\).*variables\s*\((\d+)\)",
        output,
    )
    if subsystem_match:
        diag["subsystem_imbalance"] = {
            "equations": int(subsystem_match.group(1)),
            "variables": int(subsystem_match.group(2)),
        }

    if "The simulation finished successfully" in output:
        diag["simulation"] = "OK"
    elif "Failed to build model" in output:
        diag["simulation"] = "BUILD_FAILED"
    elif 'resultFile = ""' in output:
        diag["simulation"] = "NO_RESULT"

    return diag


def _dispatch_workspace_tool(
    *,
    name: str,
    arguments: dict[str, Any],
    workspace: Path,
    candidate_paths: dict[str, Path],
    candidate_meta: dict[str, dict[str, Any]],
    deficit_state: dict[str, int] | None = None,
) -> str:
    candidate_id = _safe_candidate_id(str(arguments.get("candidate_id") or "candidate"))

    if name == "list_workspace_files":
        items: list[dict[str, Any]] = []
        if workspace.exists():
            for p in sorted(workspace.rglob("*")):
                if p.is_file():
                    rel = str(p.relative_to(workspace))
                    items.append({
                        "path": rel,
                        "size": p.stat().st_size,
                        "type": p.suffix,
                    })
        return json.dumps({"files": items}, sort_keys=True)

    if name == "read_file":
        file_path = str(arguments.get("path") or "").strip()
        if not file_path:
            return json.dumps({"error": "path required"}, sort_keys=True)
        full_path = (workspace / file_path).resolve()
        if not full_path.is_relative_to(workspace.resolve()):
            return json.dumps({"error": "path traversal denied", "path": file_path}, sort_keys=True)
        if not full_path.exists():
            return json.dumps({"error": "file not found", "path": file_path}, sort_keys=True)
        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception:
            content = full_path.read_text(encoding="latin-1")
        return content

    if name == "write_and_check_candidate_model":
        model_text = str(arguments.get("model_text") or "")
        if not model_text.strip():
            return json.dumps({"error": "model_text required"}, sort_keys=True)
        path = workspace / f"{candidate_id}.mo"
        path.write_text(model_text, encoding="utf-8")
        candidate_paths[candidate_id] = path
        output, check_ok, simulate_ok = _run_omc_check(workspace=workspace, candidate_path=path)
        omc_output_path = workspace / f"{candidate_id}.omc.txt"
        omc_output_path.write_text(str(output or ""), encoding="utf-8")
        candidate_meta[candidate_id] = {
            "candidate_id": candidate_id,
            "path": str(path),
            "rationale": str(arguments.get("rationale") or ""),
            "model_name": _extract_model_name(model_text),
            "write_check_ok": bool(check_ok),
            "write_simulate_ok": bool(simulate_ok),
            "omc_output_path": str(omc_output_path),
        }
        eq_match = re.search(r"(\d+)\s+equation\(s\)\s+and\s+(\d+)\s+variable\(s\)", str(output or ""))
        eq_count = int(eq_match.group(1)) if eq_match else 0
        var_count = int(eq_match.group(2)) if eq_match else 0
        current_deficit = 0
        if eq_count and var_count:
            current_deficit = var_count - eq_count
        deficit_delta = ""
        if deficit_state is not None and isinstance(deficit_state.get("last_deficit"), int):
            prev = int(deficit_state["last_deficit"])
            delta = current_deficit - prev
            if delta < 0:
                deficit_delta = f" (deficit ↓ by {abs(delta)}: {prev}→{current_deficit})"
            elif delta > 0:
                deficit_delta = f" (deficit ↑ by {delta}: {prev}→{current_deficit})"
            elif prev != current_deficit:
                deficit_delta = f" (deficit unchanged: {current_deficit})"
        if deficit_state is not None:
            deficit_state["last_deficit"] = current_deficit
        eq_balance = f"{eq_count} equations, {var_count} variables"
        if eq_count and var_count:
            if eq_count < var_count:
                eq_balance += f" — UNDER-DETERMINED (need {var_count - eq_count} more equations){deficit_delta}"
            elif eq_count > var_count:
                eq_balance += f" — OVER-DETERMINED ({eq_count - var_count} extra equations){deficit_delta}"
            else:
                eq_balance += " — BALANCED"
                sim_output = str(output or "")
                if "Failed to build model" in sim_output:
                    eq_balance += " but simulation build FAILED"
                elif "imbalanced number of equations" in sim_output:
                    eq_balance += " but simulation has SUBSYSTEM IMBALANCE — structural issue remains"
                elif 'resultFile = ""' in sim_output:
                    eq_balance += " but simulation produced no result file"
        return json.dumps(
            {
                "status": "written_and_checked",
                "candidate_id": candidate_id,
                "path": str(path),
                "check_ok": bool(check_ok),
                "simulate_ok": bool(simulate_ok),
                "equation_balance": eq_balance,
                "diagnostics": _extract_omc_diagnostics(str(output or "")),
                "omc_output": str(output or "")[:3000],
                "omc_output_path": str(omc_output_path),
                "auto_repair": False,
                "auto_submit": False,
                "candidate_selected": False,
            },
            sort_keys=True,
        )

    if name == "update_repair_progress":
        todos = arguments.get("todos") if isinstance(arguments.get("todos"), list) else []
        return json.dumps({
            "status": "recorded",
            "todo_count": len(todos),
            "completed": sum(1 for t in todos if isinstance(t, dict) and t.get("status") == "completed"),
            "in_progress": sum(1 for t in todos if isinstance(t, dict) and t.get("status") == "in_progress"),
            "pending": sum(1 for t in todos if isinstance(t, dict) and t.get("status") == "pending"),
        }, sort_keys=True)

    if name == "batch_check_candidates":
        candidates = arguments.get("candidates") if isinstance(arguments.get("candidates"), list) else []
        results: list[dict[str, Any]] = []
        for cand in candidates[:6]:
            if not isinstance(cand, dict):
                continue
            cid = _safe_candidate_id(str(cand.get("candidate_id") or "batch_candidate"))
            model_text = str(cand.get("model_text") or "")
            if not model_text.strip():
                continue
            path = workspace / f"{cid}.mo"
            path.write_text(model_text, encoding="utf-8")
            candidate_paths[cid] = path
            output, check_ok, simulate_ok = _run_omc_check(workspace=workspace, candidate_path=path)
            omc_output_path = workspace / f"{cid}.omc.txt"
            omc_output_path.write_text(str(output or ""), encoding="utf-8")
            candidate_meta[cid] = {
                "candidate_id": cid,
                "path": str(path),
                "rationale": str(cand.get("rationale", "")),
                "model_name": _extract_model_name(model_text),
                "write_check_ok": bool(check_ok),
                "write_simulate_ok": bool(simulate_ok),
                "omc_output_path": str(omc_output_path),
            }
            eq_match = re.search(r"(\d+)\s+equation\(s\)\s+and\s+(\d+)\s+variable\(s\)", str(output or ""))
            eq_count = int(eq_match.group(1)) if eq_match else 0
            var_count = int(eq_match.group(2)) if eq_match else 0
            results.append({
                "candidate_id": cid,
                "rationale": str(cand.get("rationale", ""))[:80],
                "check_ok": bool(check_ok),
                "simulate_ok": bool(simulate_ok),
                "equations": eq_count,
                "variables": var_count,
                "balance": f"{eq_count}eq/{var_count}var",
                "deficit": var_count - eq_count,
                "omc_output_path": str(omc_output_path),
            })
        return json.dumps({"batch_results": results, "total": len(results)}, sort_keys=True)

    if candidate_id not in candidate_paths:
        return json.dumps({"error": "unknown_candidate_id", "candidate_id": candidate_id}, sort_keys=True)

    path = candidate_paths[candidate_id]

    if name == "submit_candidate_model":
        return json.dumps({"status": "submitted", "candidate_id": candidate_id}, sort_keys=True)

    return json.dumps({"error": "unknown_tool", "tool": name}, sort_keys=True)


def run_workspace_style_case(
    case: dict[str, Any],
    *,
    out_dir: Path,
    max_steps: int = 10,
    max_token_budget: int = 32000,
    planner_backend: str = "auto",
    preload_diagnostics: str | None = None,
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    model_name = str(case["model_name"])
    current_text = str(case["model_text"])
    workflow_goal = str(case.get("workflow_goal") or "")
    case_workspace = (out_dir / "workspaces" / case_id).resolve()
    case_workspace.mkdir(parents=True, exist_ok=True)
    (case_workspace / "initial.mo").write_text(current_text, encoding="utf-8")

    adapter, config = resolve_provider_adapter(planner_backend)
    provider = config.provider_name
    if provider == "rule":
        return {
            "case_id": case_id,
            "model_name": model_name,
            "provider": provider,
            "final_verdict": "FAILED",
            "provider_error": "rule_backend_selected",
            "submitted": False,
            "steps": [],
            "candidate_files": [],
        }

    if preload_diagnostics:
        system_prompt = (
            "You are making a Modelica model work.\n"
            "Pre-computed diagnostics are provided below — no exploration needed.\n"
            "Strategy: analyze diagnostics → fix → verify.\n"
            "1. Read the diagnostics to understand exactly which variables lack equations.\n"
            "2. Write ONE precise candidate with write_and_check_candidate_model.\n"
            "3. If check or simulation fails, refine and write ONE more candidate.\n"
            "4. When a candidate passes both, submit with submit_candidate_model.\n\n"
            "Common Modelica repair patterns:\n"
            "- Under-determined: add zero-flow equations for unused connector flows (pin.i = 0)\n"
            "- For MSL measurement probes: set p.i = 0; n.i = 0;\n"
            "- Over-determined: remove or modify conflicting equations\n"
            "- Structural mismatch: add redundant equation (e.g., Ohm's law) to help OMC matching\n\n"
            "Equation deficit tracking:\n"
            "- After each check, compare the equation deficit to the PREVIOUS candidate.\n"
            "- If deficit ↓: last change was effective — keep it and refine.\n"
            "- If deficit ↑ or unchanged: last change was ineffective — revert it.\n"
            "- Combine effective changes. Do NOT restart from the original model.\n"
            "- The goal is to progressively reduce the deficit to zero.\n"
        )
        env_prefix = (
            "Pre-computed diagnostics are provided below. No need to explore the workspace.\n\n"
        )
    else:
        system_prompt = (
            "You are making a Modelica model work using a file workspace.\n\n"
            "Strategy: explore → plan → analyze → fix → verify.\n"
            "1. First, explore with list_workspace_files and read_file.\n"
            "2. Plan your repair strategy with update_repair_progress.\n"
            "3. Run write_and_check_candidate_model on the initial model.\n"
            "4. Analyze the diagnostics field: unconstrained_variables tells exactly which pins need equations.\n"
            "5. Form a complete fix plan BEFORE writing any modified candidate.\n"
            "6. Write ONE precise candidate. Do not write multiple untested candidates.\n"
            "7. When a candidate passes both check and simulation, submit with submit_candidate_model.\n\n"
            "Common Modelica repair patterns:\n"
            "- Under-determined: add zero-flow equations for unused connector flows (pin.i = 0)\n"
            "- For MSL measurement probes (PositivePin p, NegativePin n): set p.i = 0; n.i = 0;\n"
            "- Over-determined: remove or modify conflicting equations\n"
            "- Structural: replace custom Pin connectors with MSL PositivePin/NegativePin — "
            "MSL connectors have better OMC compiler support and resolve matching issues\n\n"
            "Using diagnostics:\n"
            "- The \"unconstrained_variables\" list shows exactly which pins lack equations. Fix those directly.\n"
            "- If diagnosis shows subsystem_imbalance: structural mismatch needs a redundant equation "
            "to help OMC's BLT matching (e.g., add an explicit Ohm's law).\n"
            "- Cross-reference unconstrained variables with the Flow sum equations to understand topology.\n\n"
            "The harness will not generate repairs, choose candidates, or submit automatically.\n\n"
            "Equation deficit tracking:\n"
            "- After each check, compare the equation deficit to the PREVIOUS candidate.\n"
            "- If deficit ↓: your last change was effective — keep it and refine further.\n"
            "- If deficit ↑ or unchanged: your last change was ineffective — revert it.\n"
            "- Combine effective changes. Do NOT restart from the original model each time.\n"
            "- When a remove removes equations, also add compensating equations in the SAME candidate.\n"
            "- The goal is to progressively reduce the deficit from its initial value to zero.\n"
        )
        env_prefix = (
            "Environment: OMC openmodelica:v1.26.1-minimal.\n"
            "MSL components: Modelica.Electrical.Analog.Interfaces.(PositivePin, NegativePin), "
            "Modelica.Electrical.Analog.Basic.(Ground, Resistor, Capacitor, Inductor), "
            "Modelica.Electrical.Analog.Sources.(ConstantVoltage, StepVoltage, ...).\n"
            "You may replace custom connectors with MSL equivalents to simplify the model.\n\n"
        )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"{env_prefix}"
                + (f"{preload_diagnostics}\n\n" if preload_diagnostics else "")
                + f"Task: {workflow_goal}\n\n"
                f"Model name: {model_name}\n"
                f"Workspace initial file: initial.mo\n\n"
                f"Initial model:\n-----BEGIN_MODEL-----\n{current_text}\n-----END_MODEL-----\n"
            ),
        },
    ]
    candidate_paths: dict[str, Path] = {}
    candidate_meta: dict[str, dict[str, Any]] = {}
    steps: list[dict[str, Any]] = []
    token_used = 0
    submitted_id = ""
    provider_error = ""
    invalid_submission_attempts: list[dict[str, Any]] = []
    deficit_state: dict[str, int] = {}
    compaction_done = False

    for step_idx in range(1, max(1, int(max_steps)) + 1):
        resp, err = adapter.send_tool_request(messages, WORKSPACE_TOOL_DEFS, config)
        if err:
            provider_error = err
            steps.append({"step": step_idx, "error": err})
            break
        if resp is None:
            steps.append({"step": step_idx, "error": "null_response"})
            break
        token_used += int(resp.usage.get("total_tokens", 0))
        reasoning_text = resp.reasoning or ""

        if not compaction_done and token_used > max_token_budget * 0.85 and len(steps) >= 3:
            compaction_done = True
            summary_parts: list[str] = [f"Candidate history ({len(candidate_meta)} attempted):"]
            for _cid, meta in candidate_meta.items():
                ck = "✓" if bool(meta.get("write_check_ok")) else "✗"
                summary_parts.append(f"  {_cid}: check={ck}")
            summary_parts.append(f"Current deficit: {deficit_state.get('last_deficit', 'unknown')}")
            messages.append({
                "role": "system",
                "content": "--- SESSION SUMMARY ---\n" + "\n".join(summary_parts) + "\nFocus on remaining deficit. Combine effective changes.",
            })
            steps.append({"step": f"{step_idx}_compaction", "summary": summary_parts})

        step_record = {
            "step": step_idx,
            "text": resp.text,
            "reasoning": reasoning_text[:3000] if reasoning_text else "",
            "tool_calls": [
                {"name": tc.name, "arguments": tc.arguments}
                for tc in resp.tool_calls
            ],
            "token_used": token_used,
        }
        if resp.tool_calls:
            assistant_msg = {"role": "assistant", "content": resp.text or None}
            if reasoning_text:
                assistant_msg["reasoning_content"] = reasoning_text
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in resp.tool_calls
            ]
            messages.append(assistant_msg)
            tool_results = []
            for tc in resp.tool_calls:
                result = _dispatch_workspace_tool(
                    name=tc.name,
                    arguments=dict(tc.arguments),
                    workspace=case_workspace,
                    candidate_paths=candidate_paths,
                    candidate_meta=candidate_meta,
                    deficit_state=deficit_state,
                )
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                tool_results.append({
                    "name": tc.name,
                    "result": result,
                    "result_preview": result[:500],
                })
                if tc.name == "submit_candidate_model":
                    requested_candidate_id = _safe_candidate_id(
                        str(tc.arguments.get("candidate_id") or "")
                    )
                    try:
                        submit_payload = json.loads(result)
                    except json.JSONDecodeError:
                        submit_payload = {}
                    if (
                        submit_payload.get("status") == "submitted"
                        and requested_candidate_id in candidate_paths
                    ):
                        submitted_id = requested_candidate_id
                    else:
                        invalid_submission_attempts.append({
                            "candidate_id": requested_candidate_id,
                            "result": result,
                        })
            step_record["tool_results"] = tool_results
        else:
            messages.append({"role": "assistant", "content": resp.text})
        steps.append(step_record)
        if submitted_id or token_used >= max_token_budget:
            break

    final_model_text = ""
    final_verdict = "FAILED"

    if submitted_id and submitted_id in candidate_paths:
        final_model_text = candidate_paths[submitted_id].read_text(encoding="utf-8")
        final_output = _run_omc_simulate(
            workspace=case_workspace,
            candidate_path=candidate_paths[submitted_id],
            stop_time=float(case.get("final_stop_time") or 0.05),
            intervals=int(case.get("final_intervals") or 5),
        )
        check_ok = "record SimulationResult" in final_output and 'resultFile = ""' not in final_output
        simulate_ok = "The simulation finished successfully" in final_output
        final_verdict = "PASS" if check_ok and simulate_ok else "FAILED"
        steps.append(
            {
                "step": "final_eval",
                "candidate_id": submitted_id,
                "check_ok": check_ok,
                "simulate_ok": simulate_ok,
                "omc_output": str(final_output or "")[:2000],
            }
        )

    return {
        "case_id": case_id,
        "model_name": model_name,
        "provider": provider,
        "run_mode": "workspace_style_tool_use",
        "tool_count": len(WORKSPACE_TOOL_DEFS),
        "final_verdict": final_verdict,
        "submitted": bool(submitted_id),
        "submitted_candidate_id": submitted_id,
        "submission_mode": "llm" if submitted_id else "none",
        "step_count": len(steps),
        "token_used": token_used,
        "provider_error": provider_error,
        "candidate_files": list(candidate_meta.values()),
        "steps": steps,
        "final_model_text": final_model_text,
        "invalid_submission_attempt_count": len(invalid_submission_attempts),
        "invalid_submission_attempts": invalid_submission_attempts,
        "submit_checkpoint_triggered": False,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "wrapper_auto_submit_added": False,
            "llm_submit_required": True,
        },
    }


RunWorkspaceCaseFn = Callable[..., dict[str, Any]]


def _candidate_file_audit(
    case_workspace: Path,
    *,
    exclude_stems: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not case_workspace.exists():
        return []
    excluded = set(exclude_stems or set())
    rows: list[dict[str, Any]] = []
    for path in sorted(case_workspace.glob("*.mo")):
        if path.name in {"initial.mo"}:
            continue
        if path.stem in excluded:
            continue
        text = path.read_text(encoding="utf-8")
        rows.append(
            {
                "candidate_id": path.stem,
                "path": str(path),
                "model_name": _extract_model_name(text),
                "byte_count": len(text.encode("utf-8")),
            }
        )
    return rows


def _timeout_result(
    case: dict[str, Any],
    *,
    timeout_sec: int,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    case_workspace = (
        (out_dir / "workspaces" / str(case.get("case_id") or "")).resolve() if out_dir else Path()
    )
    model_name = str(case.get("model_name") or "")
    return {
        "case_id": str(case.get("case_id") or ""),
        "model_name": str(case.get("model_name") or ""),
        "provider": "",
        "run_mode": "workspace_style_tool_use",
        "tool_count": len(WORKSPACE_TOOL_DEFS),
        "final_verdict": "FAILED_TIMEOUT",
        "submitted": False,
        "submitted_candidate_id": "",
        "step_count": 0,
        "token_used": 0,
        "provider_error": "",
        "harness_timeout": True,
        "timeout_sec": int(timeout_sec),
        "candidate_files": (
            _candidate_file_audit(case_workspace, exclude_stems={model_name}) if out_dir else []
        ),
        "steps": [],
        "final_model_text": "",
        "submit_checkpoint_triggered": False,
        "submission_mode": "none",
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "wrapper_auto_submit_added": False,
            "llm_submit_required": True,
        },
    }


def _case_worker(
    queue: mp.Queue,
    case: dict[str, Any],
    out_dir: str,
    max_steps: int,
    max_token_budget: int,
    planner_backend: str,
    run_case_fn: RunWorkspaceCaseFn,
) -> None:
    try:
        result = run_case_fn(
            case,
            out_dir=Path(out_dir),
            max_steps=max_steps,
            max_token_budget=max_token_budget,
            planner_backend=planner_backend,
        )
        queue.put({"ok": True, "result": result})
    except Exception as exc:
        queue.put({"ok": False, "error": f"{type(exc).__name__}:{exc}"})


def _run_case_with_timeout(
    case: dict[str, Any],
    *,
    out_dir: Path,
    max_steps: int,
    max_token_budget: int,
    planner_backend: str,
    timeout_sec: int,
    run_case_fn: RunWorkspaceCaseFn,
) -> dict[str, Any]:
    if timeout_sec <= 0:
        return run_case_fn(
            case,
            out_dir=out_dir,
            max_steps=max_steps,
            max_token_budget=max_token_budget,
            planner_backend=planner_backend,
        )
    queue: mp.Queue = mp.Queue()
    proc = mp.Process(
        target=_case_worker,
        args=(queue, case, str(out_dir), max_steps, max_token_budget, planner_backend, run_case_fn),
    )
    proc.start()
    proc.join(timeout=max(1, int(timeout_sec)))
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=5)
        return _timeout_result(case, timeout_sec=timeout_sec, out_dir=out_dir)
    if queue.empty():
        result = _timeout_result(case, timeout_sec=timeout_sec, out_dir=out_dir)
        result["final_verdict"] = "FAILED_RUNNER_ERROR"
        result["harness_timeout"] = False
        result["runner_error"] = "subprocess_returned_no_result"
        return result
    payload = queue.get()
    if payload.get("ok"):
        result = dict(payload.get("result") or {})
        result["harness_timeout"] = False
        return result
    result = _timeout_result(case, timeout_sec=timeout_sec, out_dir=out_dir)
    result["final_verdict"] = "FAILED_RUNNER_ERROR"
    result["harness_timeout"] = False
    result["runner_error"] = str(payload.get("error") or "")
    return result


def load_holdout_tasks(path: Path = DEFAULT_TASKS) -> list[dict[str, Any]]:
    return sorted(
        [row for row in load_jsonl(path) if str(row.get("dataset_split") or "") == "holdout"],
        key=lambda row: str(row.get("case_id") or ""),
    )


def run_workspace_style_probe(
    *,
    tasks_path: Path = DEFAULT_TASKS,
    out_dir: Path = DEFAULT_OUT_DIR,
    case_ids: list[str] | None = None,
    limit: int = 0,
    max_steps: int = 10,
    max_token_budget: int = 32000,
    planner_backend: str = "auto",
    per_case_timeout_sec: int = 0,
    summary_version: str = "v0.67.0",
    run_case_fn: RunWorkspaceCaseFn = run_workspace_style_case,
) -> dict[str, Any]:
    wanted = set(case_ids or [])
    tasks = load_holdout_tasks(tasks_path)
    if wanted:
        tasks = [task for task in tasks if str(task.get("case_id") or "") in wanted]
    if limit:
        tasks = tasks[: max(0, int(limit))]
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.jsonl"
    results_path.write_text("", encoding="utf-8")
    results: list[dict[str, Any]] = []
    (out_dir / "summary.json").write_text(
        json.dumps(
            _build_summary(tasks=tasks, results=[], summary_version=summary_version),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    for task in tasks:
        case = task_to_tool_use_case(task)
        if per_case_timeout_sec > 0:
            result = _run_case_with_timeout(
                case,
                out_dir=out_dir,
                max_steps=max_steps,
                max_token_budget=max_token_budget,
                planner_backend=planner_backend,
                timeout_sec=per_case_timeout_sec,
                run_case_fn=run_case_fn,
            )
        else:
            result = run_case_fn(
                case,
                out_dir=out_dir,
                max_steps=max_steps,
                max_token_budget=max_token_budget,
                planner_backend=planner_backend,
            )
        if result.get("final_verdict") == "PASS":
            behavioral = evaluate_benchmark_behavior(
                task, str(result.get("final_model_text") or "")
            )
            result["behavioral_eval"] = behavioral
            if not bool(behavioral.get("pass")):
                result["final_verdict"] = "FAILED_BEHAVIOR"
        else:
            result["behavioral_eval"] = {"pass": False, "reason": "skipped_after_structural_failure"}
        results.append(result)
        with results_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(result, sort_keys=True) + "\n")
        (out_dir / "summary.json").write_text(
            json.dumps(
                _build_summary(tasks=tasks, results=results, summary_version=summary_version),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    if not tasks:
        (out_dir / "summary.json").write_text(
            json.dumps(
                _build_summary(tasks=[], results=[], summary_version=summary_version),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return load_json(out_dir / "summary.json")


def _build_summary(
    *,
    tasks: list[dict[str, Any]],
    results: list[dict[str, Any]],
    summary_version: str = "v0.67.0",
) -> dict[str, Any]:
    provider_error_count = sum(1 for row in results if row.get("provider_error"))
    timeout_count = sum(1 for row in results if row.get("harness_timeout"))
    runner_error_count = sum(1 for row in results if row.get("runner_error"))
    pass_count = sum(1 for row in results if row.get("final_verdict") == "PASS")
    candidate_file_count = sum(len(row.get("candidate_files") or []) for row in results)
    invalid_submission_attempt_count = sum(
        int(row.get("invalid_submission_attempt_count") or 0) for row in results
    )
    checkpoint_triggered_count = sum(1 for row in results if row.get("submit_checkpoint_triggered"))
    checkpoint_pass_count = sum(
        1 for row in results
        if row.get("submit_checkpoint_triggered") and row.get("final_verdict") == "PASS"
    )
    llm_submitted_pass_count = sum(
        1 for row in results
        if row.get("submission_mode") == "llm" and row.get("final_verdict") == "PASS"
    )
    return {
        "version": summary_version,
        "analysis_scope": "workspace_style_probe_merged_tools",
        "status": "PASS" if tasks else "REVIEW",
        "evidence_role": "formal_experiment",
        "artifact_complete": len(results) == len(tasks),
        "conclusion_allowed": bool(
            tasks
            and len(results) == len(tasks)
            and provider_error_count == 0
            and timeout_count == 0
            and runner_error_count == 0
            and checkpoint_triggered_count == 0
        ),
        "run_mode": "workspace_style_tool_use",
        "tool_count": len(WORKSPACE_TOOL_DEFS),
        "case_count": len(tasks),
        "completed_case_count": len(results),
        "pass_count": pass_count,
        "fail_count": len(results) - pass_count,
        "provider_error_count": provider_error_count,
        "harness_timeout_count": timeout_count,
        "runner_error_count": runner_error_count,
        "candidate_file_count": candidate_file_count,
        "invalid_submission_attempt_count": invalid_submission_attempt_count,
        "submit_checkpoint_count": checkpoint_triggered_count,
        "submit_checkpoint_pass_count": checkpoint_pass_count,
        "llm_submitted_pass_count": llm_submitted_pass_count,
        "non_llm_submitted_pass_count": pass_count - llm_submitted_pass_count,
        "case_ids": [str(task.get("case_id") or "") for task in tasks],
        "completed_case_ids": [str(row.get("case_id") or "") for row in results],
        "pass_case_ids": [
            str(row.get("case_id") or "") for row in results if row.get("final_verdict") == "PASS"
        ],
        "fail_case_ids": [
            str(row.get("case_id") or "") for row in results if row.get("final_verdict") != "PASS"
        ],
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "wrapper_auto_submit_added": False,
            "llm_submit_required": True,
            "live_submit_checkpoint_removed": True,
            "transparent_workspace_enabled": True,
            "merged_write_check_tool": True,
        },
    }
