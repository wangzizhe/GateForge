from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_workspace_style_probe_v0_67_0 import (
    WORKSPACE_TOOL_DEFS,
    _dispatch_workspace_tool,
    _run_omc_simulate,
    _safe_candidate_id,
)
from .llm_provider_adapter import resolve_provider_adapter


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "subagent_isolation_v0_69_0"

SUBAGENT_TOOL_NAMES = {"write_and_check_candidate_model", "submit_candidate_model"}
SUBAGENT_TOOL_DEFS: list[dict[str, Any]] = [
    dict(tool) for tool in WORKSPACE_TOOL_DEFS if str(tool.get("name") or "") in SUBAGENT_TOOL_NAMES
]

DISPATCH_SUBAGENT_REPAIR_TOOL_DEF: dict[str, Any] = {
    "name": "dispatch_subagent_repair",
    "description": (
        "Launch an isolated repair sub-agent for one explicit strategy. The sub-agent "
        "can write/check candidates and submit within its own session, but the main "
        "agent must explicitly decide whether to use any returned candidate."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "strategy_hint": {
                "type": "string",
                "description": (
                    "One explicit repair strategy to try. Must be different from previous "
                    "dispatched strategies."
                ),
            },
            "model_text": {
                "type": "string",
                "description": "Optional baseline model text. Defaults to the original task model.",
            },
            "diagnostic_hint": {
                "type": "string",
                "description": (
                    "Optional diagnostic context such as equation deficit, unconstrained "
                    "variables, or previous failure summary."
                ),
            },
        },
        "required": ["strategy_hint"],
    },
}


def _discipline() -> dict[str, bool]:
    return {
        "deterministic_repair_added": False,
        "hidden_routing_added": False,
        "candidate_selection_added": False,
        "wrapper_auto_submit_added": False,
        "main_agent_submit_required": True,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _safe_subagent_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in str(value or ""))
    return text[:80] or "subagent_001"


def build_subagent_tool_result(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(summary.get("status") or "completed"),
        "subagent_id": str(summary.get("subagent_id") or ""),
        "subagent_verdict": str(summary.get("subagent_verdict") or "FAILED"),
        "submitted": bool(summary.get("submitted")),
        "submitted_candidate_id": str(summary.get("submitted_candidate_id") or ""),
        "candidate_count": int(summary.get("candidate_count") or 0),
        "token_used": int(summary.get("token_used") or 0),
        "max_token_budget": int(summary.get("max_token_budget") or 0),
        "budget_exceeded": bool(summary.get("budget_exceeded")),
        "final_model_text": str(summary.get("final_model_text") or ""),
        "failure_category": str(summary.get("failure_category") or ""),
        "key_findings": str(summary.get("key_findings") or ""),
        "artifact_path": str(summary.get("artifact_path") or ""),
        "auto_repair": False,
        "auto_submit": False,
        "candidate_selected": False,
    }


def _subagent_system_prompt(strategy_hint: str, diagnostic_hint: str) -> str:
    return (
        "You are a Modelica repair sub-agent.\n\n"
        "You have exactly one strategy to try:\n"
        f"{strategy_hint}\n\n"
        "Use only this strategy. Do not explore unrelated strategies.\n"
        "You may call write_and_check_candidate_model to create and verify candidates.\n"
        "If a candidate passes check and simulation, call submit_candidate_model.\n"
        "If the strategy fails, report the failure clearly.\n\n"
        f"Diagnostic findings:\n{diagnostic_hint or '(none)'}\n\n"
        "The harness will not repair, select, or submit for you.\n"
        "Your full trajectory will be saved for audit.\n"
    )


def _save_live_subagent_artifacts(
    *,
    subagent_dir: Path,
    summary: dict[str, Any],
    trajectory: dict[str, Any],
    candidate_meta: dict[str, dict[str, Any]],
) -> None:
    _write_json(subagent_dir / "trajectory.json", trajectory)
    _write_jsonl(subagent_dir / "results.jsonl", list(candidate_meta.values()))
    _write_json(subagent_dir / "summary.json", summary)


def run_live_subagent_repair(
    *,
    case: dict[str, Any],
    out_dir: Path = DEFAULT_OUT_DIR,
    subagent_id: str = "subagent_001",
    strategy_hint: str,
    diagnostic_hint: str = "",
    max_steps: int = 6,
    max_token_budget: int = 48_000,
    planner_backend: str = "auto",
) -> dict[str, Any]:
    if not str(strategy_hint or "").strip():
        raise ValueError("strategy_hint_required")

    out_dir = out_dir.resolve()
    clean_id = _safe_subagent_id(subagent_id)
    case_id = str(case.get("case_id") or "case")
    model_name = str(case.get("model_name") or "M")
    model_text = str(case.get("model_text") or "")
    subagent_dir = out_dir / "subagents" / case_id / clean_id
    workspace = subagent_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "initial.mo").write_text(model_text, encoding="utf-8")

    adapter, config = resolve_provider_adapter(planner_backend)
    provider = config.provider_name
    if provider == "rule":
        summary = {
            "version": "v0.69.1",
            "status": "completed",
            "case_id": case_id,
            "subagent_id": clean_id,
            "strategy_hint": strategy_hint,
            "diagnostic_hint": diagnostic_hint,
            "provider": provider,
            "subagent_verdict": "FAILED",
            "provider_error": "rule_backend_selected",
            "submitted": False,
            "submitted_candidate_id": "",
        "candidate_count": 0,
        "token_used": 0,
        "max_token_budget": int(max_token_budget),
        "budget_exceeded": False,
        "timeout": False,
            "final_model_text": "",
            "failure_category": "provider_unavailable",
            "key_findings": "",
            "artifact_complete": True,
            "artifact_path": str(subagent_dir / "trajectory.json"),
            "discipline": _discipline(),
        }
        _save_live_subagent_artifacts(
            subagent_dir=subagent_dir,
            summary=summary,
            trajectory={"messages": [], "steps": [], "discipline": _discipline()},
            candidate_meta={},
        )
        return summary

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _subagent_system_prompt(strategy_hint, diagnostic_hint)},
        {
            "role": "user",
            "content": (
                f"Model name: {model_name}\n"
                f"Initial model:\n-----BEGIN_MODEL-----\n{model_text}\n-----END_MODEL-----\n"
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

    for step_idx in range(1, max(1, int(max_steps)) + 1):
        resp, err = adapter.send_tool_request(messages, SUBAGENT_TOOL_DEFS, config)
        if err:
            provider_error = err
            steps.append({"step": step_idx, "error": err})
            break
        if resp is None:
            steps.append({"step": step_idx, "error": "null_response"})
            break
        token_used += int(resp.usage.get("total_tokens", 0))
        step_record = {
            "step": step_idx,
            "text": resp.text,
            "reasoning": (resp.reasoning or "")[:3000],
            "tool_calls": [{"name": tc.name, "arguments": tc.arguments} for tc in resp.tool_calls],
            "token_used": token_used,
        }
        if resp.tool_calls:
            assistant_msg = {"role": "assistant", "content": resp.text or None}
            if resp.reasoning:
                assistant_msg["reasoning_content"] = resp.reasoning
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
                    workspace=workspace,
                    candidate_paths=candidate_paths,
                    candidate_meta=candidate_meta,
                    deficit_state=deficit_state,
                )
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                tool_results.append({"name": tc.name, "result": result, "result_preview": result[:500]})
                if tc.name == "submit_candidate_model":
                    requested_candidate_id = _safe_candidate_id(str(tc.arguments.get("candidate_id") or ""))
                    try:
                        submit_payload = json.loads(result)
                    except json.JSONDecodeError:
                        submit_payload = {}
                    if submit_payload.get("status") == "submitted" and requested_candidate_id in candidate_paths:
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
    final_eval: dict[str, Any] = {}
    if submitted_id and submitted_id in candidate_paths:
        final_model_text = candidate_paths[submitted_id].read_text(encoding="utf-8")
        final_output = _run_omc_simulate(
            workspace=workspace,
            candidate_path=candidate_paths[submitted_id],
            stop_time=float(case.get("final_stop_time") or 0.05),
            intervals=int(case.get("final_intervals") or 5),
        )
        check_ok = "record SimulationResult" in final_output and 'resultFile = ""' not in final_output
        simulate_ok = "The simulation finished successfully" in final_output
        final_verdict = "PASS" if check_ok and simulate_ok else "FAILED"
        final_eval = {
            "candidate_id": submitted_id,
            "check_ok": check_ok,
            "simulate_ok": simulate_ok,
            "omc_output": str(final_output or "")[:3000],
        }
        steps.append({"step": "final_eval", **final_eval})

    artifact_complete = bool((workspace / "initial.mo").exists())
    summary = {
        "version": "v0.69.1",
        "status": "completed",
        "case_id": case_id,
        "subagent_id": clean_id,
        "strategy_hint": strategy_hint,
        "diagnostic_hint": diagnostic_hint,
        "provider": provider,
        "subagent_verdict": final_verdict,
        "submitted": bool(submitted_id),
        "submitted_candidate_id": submitted_id,
        "candidate_count": len(candidate_meta),
        "token_used": token_used,
        "max_token_budget": int(max_token_budget),
        "budget_exceeded": token_used >= int(max_token_budget),
        "provider_error": provider_error,
        "timeout": False,
        "final_model_text": final_model_text,
        "failure_category": "" if final_verdict == "PASS" else "candidate_generation_failed",
        "key_findings": "",
        "invalid_submission_attempt_count": len(invalid_submission_attempts),
        "invalid_submission_attempts": invalid_submission_attempts,
        "final_eval": final_eval,
        "artifact_complete": artifact_complete,
        "artifact_path": str(subagent_dir / "trajectory.json"),
        "candidate_files_dir": str(workspace),
        "omc_outputs_dir": str(workspace),
        "discipline": _discipline(),
    }
    trajectory = {
        "case_id": case_id,
        "subagent_id": clean_id,
        "strategy_hint": strategy_hint,
        "diagnostic_hint": diagnostic_hint,
        "messages": messages,
        "steps": steps,
        "candidate_files": list(candidate_meta.values()),
        "discipline": _discipline(),
    }
    _save_live_subagent_artifacts(
        subagent_dir=subagent_dir,
        summary=summary,
        trajectory=trajectory,
        candidate_meta=candidate_meta,
    )
    return summary


def run_mock_subagent_repair(
    *,
    case: dict[str, Any],
    out_dir: Path = DEFAULT_OUT_DIR,
    subagent_id: str = "subagent_001",
    strategy_hint: str,
    diagnostic_hint: str = "",
    outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not str(strategy_hint or "").strip():
        raise ValueError("strategy_hint_required")

    out_dir = out_dir.resolve()
    payload = dict(outcome or {})
    clean_id = _safe_subagent_id(subagent_id)
    case_id = str(case.get("case_id") or "case")
    subagent_dir = out_dir / "subagents" / case_id / clean_id
    candidate_dir = subagent_dir / "candidate_files"
    omc_dir = subagent_dir / "omc_outputs"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    omc_dir.mkdir(parents=True, exist_ok=True)

    candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
    rows: list[dict[str, Any]] = []
    candidate_ids: set[str] = set()
    for index, raw in enumerate(candidates, start=1):
        if not isinstance(raw, dict):
            continue
        candidate_id = str(raw.get("candidate_id") or f"candidate_{index}")
        candidate_ids.add(candidate_id)
        model_text = str(raw.get("model_text") or case.get("model_text") or "")
        omc_output = str(raw.get("omc_output") or "")
        model_path = candidate_dir / f"{candidate_id}.mo"
        omc_path = omc_dir / f"{candidate_id}.omc.txt"
        model_path.write_text(model_text, encoding="utf-8")
        omc_path.write_text(omc_output, encoding="utf-8")
        rows.append(
            {
                "candidate_id": candidate_id,
                "model_path": str(model_path),
                "omc_output_path": str(omc_path),
                "check_ok": bool(raw.get("check_ok")),
                "simulate_ok": bool(raw.get("simulate_ok")),
                "submitted": bool(raw.get("submitted")),
                "rationale": str(raw.get("rationale") or ""),
            }
        )

    submitted_candidate_id = str(payload.get("submitted_candidate_id") or "")
    submitted = bool(payload.get("submitted")) and submitted_candidate_id in candidate_ids
    final_model_text = ""
    if submitted:
        final_model_text = (candidate_dir / f"{submitted_candidate_id}.mo").read_text(encoding="utf-8")

    verdict = str(payload.get("subagent_verdict") or ("PASS" if submitted else "FAILED"))
    if verdict == "PASS" and not submitted:
        verdict = "FAILED"

    trajectory = {
        "case_id": case_id,
        "subagent_id": clean_id,
        "strategy_hint": strategy_hint,
        "diagnostic_hint": diagnostic_hint,
        "messages": payload.get("messages") if isinstance(payload.get("messages"), list) else [],
        "tool_calls": payload.get("tool_calls") if isinstance(payload.get("tool_calls"), list) else [],
        "tool_results": payload.get("tool_results") if isinstance(payload.get("tool_results"), list) else [],
        "candidate_ids": sorted(candidate_ids),
        "discipline": _discipline(),
    }

    _write_json(subagent_dir / "trajectory.json", trajectory)
    _write_jsonl(subagent_dir / "results.jsonl", rows)

    artifact_complete = (
        (subagent_dir / "trajectory.json").exists()
        and (subagent_dir / "results.jsonl").exists()
        and all(Path(row["model_path"]).exists() and Path(row["omc_output_path"]).exists() for row in rows)
    )
    summary = {
        "version": "v0.69.0",
        "status": "completed" if not payload.get("timeout") else "timeout",
        "case_id": case_id,
        "subagent_id": clean_id,
        "strategy_hint": strategy_hint,
        "diagnostic_hint": diagnostic_hint,
        "subagent_verdict": verdict,
        "submitted": submitted,
        "submitted_candidate_id": submitted_candidate_id if submitted else "",
        "candidate_count": len(rows),
        "token_used": int(payload.get("token_used") or 0),
        "max_token_budget": int(payload.get("max_token_budget") or 0),
        "budget_exceeded": bool(payload.get("budget_exceeded")),
        "provider_error": str(payload.get("provider_error") or ""),
        "timeout": bool(payload.get("timeout")),
        "final_model_text": final_model_text,
        "failure_category": str(payload.get("failure_category") or ""),
        "key_findings": str(payload.get("key_findings") or ""),
        "artifact_complete": artifact_complete,
        "artifact_path": str(subagent_dir / "trajectory.json"),
        "candidate_files_dir": str(candidate_dir),
        "omc_outputs_dir": str(omc_dir),
        "discipline": _discipline(),
    }
    _write_json(subagent_dir / "summary.json", summary)
    return summary


def dispatch_subagent_repair_mock(
    *,
    arguments: dict[str, Any],
    case: dict[str, Any],
    out_dir: Path = DEFAULT_OUT_DIR,
    subagent_id: str = "subagent_001",
    outcome: dict[str, Any] | None = None,
) -> str:
    strategy_hint = str(arguments.get("strategy_hint") or "")
    model_text = str(arguments.get("model_text") or case.get("model_text") or "")
    diagnostic_hint = str(arguments.get("diagnostic_hint") or "")
    case_payload = dict(case)
    if model_text:
        case_payload["model_text"] = model_text
    summary = run_mock_subagent_repair(
        case=case_payload,
        out_dir=out_dir,
        subagent_id=subagent_id,
        strategy_hint=strategy_hint,
        diagnostic_hint=diagnostic_hint,
        outcome=outcome,
    )
    return json.dumps(build_subagent_tool_result(summary), sort_keys=True)


def build_subagent_isolation_summary(
    *,
    case_results: list[dict[str, Any]],
    case_count: int,
    budget_main: int = 0,
    budget_subagents: int = 0,
    summary_version: str = "v0.69.0",
) -> dict[str, Any]:
    subagent_count = sum(int(row.get("subagent_count") or 0) for row in case_results)
    subagent_pass_count = sum(int(row.get("subagent_pass_count") or 0) for row in case_results)
    provider_error_count = sum(int(row.get("provider_error_count") or 0) for row in case_results)
    timeout_count = sum(int(row.get("timeout_count") or 0) for row in case_results)
    artifact_complete = bool(case_count == len(case_results)) and all(
        bool(row.get("artifact_complete")) for row in case_results
    )
    wrapper_flags = []
    for row in case_results:
        discipline = row.get("discipline") if isinstance(row.get("discipline"), dict) else {}
        wrapper_flags.extend([
            bool(discipline.get("deterministic_repair_added")),
            bool(discipline.get("hidden_routing_added")),
            bool(discipline.get("candidate_selection_added")),
            bool(discipline.get("wrapper_auto_submit_added")),
        ])
    return {
        "version": summary_version,
        "analysis_scope": "subagent_isolation_contract",
        "evidence_role": "debug",
        "status": "PASS" if artifact_complete and not any(wrapper_flags) else "REVIEW",
        "conclusion_allowed": False,
        "capability_conclusion_allowed": False,
        "artifact_complete": artifact_complete,
        "case_count": int(case_count),
        "completed_case_count": len(case_results),
        "subagent_enabled": True,
        "subagent_count": subagent_count,
        "subagent_pass_count": subagent_pass_count,
        "main_agent_submitted_subagent_candidate": any(
            bool(row.get("main_agent_submitted_subagent_candidate")) for row in case_results
        ),
        "provider_error_count": provider_error_count,
        "timeout_count": timeout_count,
        "budget_main": int(budget_main),
        "budget_subagents": int(budget_subagents),
        "budget_total": int(budget_main) + int(budget_subagents),
        "budget_equalized": False,
        "discipline": _discipline(),
    }


def build_equal_budget_ab_summary(
    *,
    single_agent_summary: dict[str, Any],
    subagent_summary: dict[str, Any],
    budget_total: int,
    summary_version: str = "v0.69.2",
) -> dict[str, Any]:
    single_pass = int(single_agent_summary.get("pass_count") or 0)
    subagent_pass = int(subagent_summary.get("subagent_pass_count") or 0)
    provider_error_count = int(single_agent_summary.get("provider_error_count") or 0) + int(
        subagent_summary.get("provider_error_count") or 0
    )
    timeout_count = int(single_agent_summary.get("harness_timeout_count") or 0) + int(
        subagent_summary.get("timeout_count") or 0
    )
    budget_exceeded_count = int(bool(single_agent_summary.get("budget_exceeded"))) + int(
        bool(subagent_summary.get("budget_exceeded"))
    )
    artifact_complete = bool(single_agent_summary.get("artifact_complete")) and bool(
        subagent_summary.get("artifact_complete")
    )
    capability_allowed = bool(
        artifact_complete
        and provider_error_count == 0
        and timeout_count == 0
        and budget_exceeded_count == 0
    )
    if capability_allowed and subagent_pass > single_pass:
        decision = "isolation_gain_candidate"
    elif capability_allowed and subagent_pass == single_pass:
        decision = "no_measurable_isolation_gain"
    elif capability_allowed:
        decision = "single_agent_better"
    else:
        decision = "incomplete_or_provider_blocked"
    return {
        "version": summary_version,
        "analysis_scope": "subagent_equal_budget_ab",
        "evidence_role": "formal_experiment" if capability_allowed else "debug",
        "status": "PASS" if artifact_complete else "REVIEW",
        "conclusion_allowed": capability_allowed,
        "capability_conclusion_allowed": capability_allowed,
        "artifact_complete": artifact_complete,
        "budget_equalized": True,
        "budget_total": int(budget_total),
        "single_agent_pass_count": single_pass,
        "subagent_pass_count": subagent_pass,
        "provider_error_count": provider_error_count,
        "timeout_count": timeout_count,
        "budget_exceeded_count": budget_exceeded_count,
        "decision": decision,
        "budget_gain_excluded": capability_allowed,
        "discipline": _discipline(),
    }


def build_parallel_subagent_gate_summary(
    *,
    equal_budget_summary: dict[str, Any],
    summary_version: str = "v0.69.3",
) -> dict[str, Any]:
    isolation_signal = str(equal_budget_summary.get("decision") or "") == "isolation_gain_candidate"
    return {
        "version": summary_version,
        "analysis_scope": "parallel_subagent_gate",
        "evidence_role": "debug",
        "status": "PASS" if isolation_signal else "HOLD",
        "conclusion_allowed": False,
        "parallel_allowed": isolation_signal,
        "reason": (
            "equal_budget_isolation_signal_present"
            if isolation_signal else "wait_for_equal_budget_isolation_signal"
        ),
        "discipline": _discipline(),
    }


def build_hard_pack_subagent_readiness_summary(
    *,
    contract_summary: dict[str, Any],
    equal_budget_summary: dict[str, Any],
    provider_stable: bool,
    summary_version: str = "v0.69.4",
) -> dict[str, Any]:
    ready = bool(
        contract_summary.get("artifact_complete")
        and equal_budget_summary.get("capability_conclusion_allowed")
        and provider_stable
    )
    return {
        "version": summary_version,
        "analysis_scope": "hard_pack_subagent_readiness",
        "evidence_role": "debug",
        "status": "PASS" if ready else "HOLD",
        "conclusion_allowed": False,
        "hard_pack_eval_allowed": ready,
        "provider_stable": bool(provider_stable),
        "contract_artifact_complete": bool(contract_summary.get("artifact_complete")),
        "equal_budget_conclusion_allowed": bool(equal_budget_summary.get("capability_conclusion_allowed")),
        "discipline": _discipline(),
    }


def run_subagent_contract_probe(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    case: dict[str, Any] | None = None,
    outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    case_payload = dict(case or {
        "case_id": "mock_case",
        "model_name": "M",
        "model_text": "model M\nend M;\n",
    })
    sub_summary = run_mock_subagent_repair(
        case=case_payload,
        out_dir=out_dir,
        strategy_hint="mock isolated repair strategy",
        outcome=outcome,
    )
    case_result = {
        "case_id": case_payload["case_id"],
        "artifact_complete": bool(sub_summary.get("artifact_complete")),
        "subagent_count": 1,
        "subagent_pass_count": 1 if sub_summary.get("subagent_verdict") == "PASS" else 0,
        "provider_error_count": 1 if sub_summary.get("provider_error") else 0,
        "timeout_count": 1 if sub_summary.get("timeout") else 0,
        "main_agent_submitted_subagent_candidate": False,
        "discipline": _discipline(),
    }
    summary = build_subagent_isolation_summary(case_results=[case_result], case_count=1)
    _write_json(out_dir / "summary.json", summary)
    return summary
