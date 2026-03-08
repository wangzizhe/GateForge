from __future__ import annotations

import json
import re
from typing import Callable

from .agent_modelica_action_applier_v0 import apply_repair_actions_to_modelica_v0
from .agent_modelica_diagnostic_ir_v0 import build_diagnostic_ir_v0
from .agent_modelica_error_action_mapper_v1 import map_error_to_actions
from .agent_modelica_modeling_ir_v0 import DEFAULT_COMPONENT_WHITELIST, modelica_to_ir
from .agent_modelica_orchestrator_guard_v0 import detect_no_progress_v0, prioritize_repair_actions_v0
from .agent_modelica_repair_action_ir_v0 import validate_action_batch_v0
from .agent_modelica_repair_action_policy_v0 import recommend_repair_actions_v0
from .agent_modelica_repair_memory_v2 import summarize_action_effectiveness_v2
from .agent_modelica_retrieval_augmented_repair_v1 import retrieve_repair_examples


SCHEMA_VERSION = "agent_modelica_l4_orchestrator_v0"


def _merge_actions(*rows: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for item in row:
            text = str(item or "").strip()
            if text and text not in seen:
                out.append(text)
                seen.add(text)
    return out


def _candidate_ports(ir_payload: dict) -> list[str]:
    out: list[str] = []
    components = ir_payload.get("components") if isinstance(ir_payload.get("components"), list) else []
    for row in components:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "").strip()
        if not cid:
            continue
        for port in ("p", "n", "v", "i"):
            out.append(f"{cid}.{port}")
    return out


def _infer_numeric_value(action_text: str, default: float) -> float:
    m = re.search(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?", str(action_text or ""))
    if not m:
        return float(default)
    try:
        return float(m.group(0))
    except Exception:
        return float(default)


def _build_rule_action_from_text(
    *,
    action_id: str,
    action_text: str,
    ir_payload: dict,
    source: str,
    confidence: float,
) -> dict | None:
    lower = str(action_text or "").strip().lower()
    components = ir_payload.get("components") if isinstance(ir_payload.get("components"), list) else []
    connections = ir_payload.get("connections") if isinstance(ir_payload.get("connections"), list) else []
    if not components:
        return None

    # connection-first when diagnostic explicitly hints connector issues
    if ("connector" in lower or "connect" in lower) and connections:
        row = connections[0] if isinstance(connections[0], dict) else {}
        return {
            "action_id": action_id,
            "op": "disconnect_ports",
            "target": {"from": str(row.get("from") or ""), "to": str(row.get("to") or "")},
            "args": {},
            "reason_tag": "connector_repair",
            "source": source,
            "confidence": confidence,
        }
    if ("connector" in lower or "connect" in lower) and not connections:
        ports = _candidate_ports(ir_payload)
        if len(ports) >= 2:
            return {
                "action_id": action_id,
                "op": "connect_ports",
                "target": {"from": ports[0], "to": ports[1]},
                "args": {},
                "reason_tag": "connector_repair",
                "source": source,
                "confidence": confidence,
            }

    if "replace" in lower or "component" in lower:
        base = next((x for x in components if isinstance(x, dict) and str(x.get("id") or "").strip()), None)
        if isinstance(base, dict):
            cid = str(base.get("id") or "")
            current_type = str(base.get("type") or "")
            new_type = "Modelica.Electrical.Analog.Basic.Resistor"
            if current_type == new_type:
                new_type = "Modelica.Electrical.Analog.Basic.Capacitor"
            return {
                "action_id": action_id,
                "op": "replace_component",
                "target": {"component_id": cid},
                "args": {"new_type": new_type},
                "reason_tag": "component_replace",
                "source": source,
                "confidence": confidence,
            }

    base = next((x for x in components if isinstance(x, dict) and str(x.get("id") or "").strip()), None)
    if not isinstance(base, dict):
        return None
    cid = str(base.get("id") or "")
    ctype = str(base.get("type") or "")
    params = base.get("params") if isinstance(base.get("params"), dict) else {}
    param_keys = [str(x) for x in params.keys()]
    if not param_keys:
        # fall back to semantic map when no params are set yet
        from .agent_modelica_electrical_msl_semantics_v0 import allowed_ir_param_names

        param_keys = allowed_ir_param_names(ctype)
    if not param_keys:
        return None
    key = str(param_keys[0])
    default_value = params.get(key, 1.0)
    next_value = _infer_numeric_value(lower, default=float(default_value) if isinstance(default_value, (int, float)) else 1.0)

    if "start" in lower or "initial" in lower:
        return {
            "action_id": action_id,
            "op": "set_start_value",
            "target": {"component_id": cid, "variable": key, "parameter": key},
            "args": {"value": next_value},
            "reason_tag": "initialization_repair",
            "source": source,
            "confidence": confidence,
        }
    return {
        "action_id": action_id,
        "op": "set_parameter",
        "target": {"component_id": cid, "parameter": key},
        "args": {"value": next_value},
        "reason_tag": "parameter_repair",
        "source": source,
        "confidence": confidence,
    }


def build_l4_action_plan_v0(
    *,
    task: dict,
    diagnostic_payload: dict,
    modelica_text: str,
    fallback_actions: list[str],
    repair_history_payload: dict,
    retrieval_policy_payload: dict,
    policy_backend: str,
    max_actions_per_round: int,
) -> dict:
    failure_type = str(task.get("failure_type") or "")
    expected_stage = str(task.get("expected_stage") or "")
    error_text = " | ".join(
        [
            str(diagnostic_payload.get("reason") or ""),
            str(task.get("error_message") or ""),
            str(task.get("compile_error") or ""),
            str(task.get("simulate_error_message") or ""),
            str(task.get("stderr_snippet") or ""),
        ]
    )
    mapped = map_error_to_actions(error_text, failure_type=failure_type)
    retrieved = retrieve_repair_examples(
        history_payload=repair_history_payload if isinstance(repair_history_payload, dict) else {},
        failure_type=failure_type,
        model_hint=str(task.get("source_model_path") or task.get("mutated_model_path") or ""),
        top_k=2,
        policy_payload=retrieval_policy_payload if isinstance(retrieval_policy_payload, dict) else {},
    )
    policy = recommend_repair_actions_v0(
        failure_type=failure_type,
        expected_stage=expected_stage,
        diagnostic_payload=diagnostic_payload if isinstance(diagnostic_payload, dict) else {},
        fallback_actions=[str(x) for x in (fallback_actions or []) if isinstance(x, str)],
    )
    merged_actions = _merge_actions(
        [str(x) for x in (policy.get("actions") or []) if isinstance(x, str)],
        [str(x) for x in (mapped.get("actions") or []) if isinstance(x, str)],
        [str(x) for x in (retrieved.get("suggested_actions") or []) if isinstance(x, str)],
        [str(x) for x in (fallback_actions or []) if isinstance(x, str)],
    )
    ordered_actions = prioritize_repair_actions_v0(merged_actions, expected_stage=expected_stage)
    selected_text_actions = ordered_actions[: max(1, int(max_actions_per_round))]

    source = "rule"
    if not selected_text_actions and str(policy_backend or "").strip().lower() == "llm":
        # v1 keeps deterministic fallback and only tags as llm-backfilled.
        selected_text_actions = [str(x) for x in (fallback_actions or []) if isinstance(x, str)][: max(1, int(max_actions_per_round))]
        source = "llm"

    try:
        ir_payload = modelica_to_ir(str(modelica_text or ""))
    except Exception as exc:
        return {
            "status": "FAIL",
            "plan_error_code": "modelica_to_ir_failed",
            "errors": [str(exc)],
            "actions_text": selected_text_actions,
            "actions_ir": [],
        }

    actions_ir: list[dict] = []
    for idx, text in enumerate(selected_text_actions, start=1):
        action = _build_rule_action_from_text(
            action_id=f"l4_{idx}",
            action_text=text,
            ir_payload=ir_payload,
            source=source,
            confidence=0.72 if source == "rule" else 0.62,
        )
        if isinstance(action, dict):
            actions_ir.append(action)

    validation = validate_action_batch_v0(
        actions_payload=actions_ir,
        ir_payload=ir_payload,
        max_actions_per_round=max(1, int(max_actions_per_round)),
        allowed_component_types=DEFAULT_COMPONENT_WHITELIST,
    )
    normalized = validation.get("normalized_actions") if isinstance(validation.get("normalized_actions"), list) else []
    return {
        "status": "PASS" if validation.get("status") == "PASS" and normalized else "FAIL",
        "plan_error_code": "" if validation.get("status") == "PASS" and normalized else "action_plan_invalid",
        "errors": list(validation.get("errors") or []),
        "rejected_actions": list(validation.get("rejected_actions") or []),
        "actions_text": selected_text_actions,
        "actions_ir": normalized,
        "policy_channel": str(policy.get("channel") or ""),
        "retrieved_count": int(retrieved.get("retrieved_count", 0) or 0),
    }


def run_l4_orchestrator_v0(
    *,
    task: dict,
    initial_model_text: str,
    initial_actions: list[str],
    run_attempt: Callable[[int, str, list[str]], dict],
    max_rounds: int = 3,
    max_time_sec: int = 180,
    max_actions_per_round: int = 3,
    no_progress_window: int = 2,
    policy_backend: str = "rule",
    repair_history_payload: dict | None = None,
    retrieval_policy_payload: dict | None = None,
) -> dict:
    rounds = max(1, int(max_rounds))
    time_budget = max(1, int(max_time_sec))
    current_text = str(initial_model_text or "")
    current_actions = [str(x) for x in (initial_actions or []) if isinstance(x, str)]

    attempts: list[dict] = []
    trajectory_rows: list[dict] = []
    elapsed_total = 0.0
    passed = False
    stop_reason = "max_rounds_reached"
    rounds_used = 0
    hard_checks = {
        "check_model_pass": False,
        "simulate_pass": False,
        "physics_contract_pass": False,
        "regression_pass": False,
    }

    for round_idx in range(1, rounds + 1):
        rounds_used = round_idx
        attempt = run_attempt(round_idx, current_text, current_actions)
        attempt = attempt if isinstance(attempt, dict) else {}
        attempt.setdefault("round", round_idx)
        elapsed_total += float(attempt.get("elapsed_sec") or 0.0)

        check_ok = bool(attempt.get("check_model_pass"))
        simulate_ok = bool(attempt.get("simulate_pass"))
        physics_ok = bool(attempt.get("physics_contract_pass"))
        regression_ok = bool(attempt.get("regression_pass"))
        hard_checks = {
            "check_model_pass": check_ok,
            "simulate_pass": simulate_ok,
            "physics_contract_pass": physics_ok,
            "regression_pass": regression_ok,
        }
        attempts.append(attempt)
        if all(hard_checks.values()):
            passed = True
            stop_reason = "hard_checks_pass"
            break
        if elapsed_total > float(time_budget):
            stop_reason = "time_budget_exceeded"
            break
        if detect_no_progress_v0(attempts, window=max(2, int(no_progress_window))):
            stop_reason = "no_progress_window"
            break

        diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
        if not diagnostic:
            diagnostic = build_diagnostic_ir_v0(
                output=" | ".join(
                    [
                        str(attempt.get("stderr_snippet") or ""),
                        str(attempt.get("reason") or ""),
                        str(attempt.get("log_excerpt") or ""),
                    ]
                ),
                check_model_pass=check_ok,
                simulate_pass=simulate_ok,
                expected_stage=str(task.get("expected_stage") or ""),
                declared_failure_type=str(task.get("failure_type") or ""),
            )

        plan = build_l4_action_plan_v0(
            task=task,
            diagnostic_payload=diagnostic,
            modelica_text=current_text,
            fallback_actions=current_actions,
            repair_history_payload=repair_history_payload if isinstance(repair_history_payload, dict) else {},
            retrieval_policy_payload=retrieval_policy_payload if isinstance(retrieval_policy_payload, dict) else {},
            policy_backend=str(policy_backend or "rule"),
            max_actions_per_round=max(1, int(max_actions_per_round)),
        )
        trajectory_row = {
            "task_id": str(task.get("task_id") or ""),
            "round": round_idx,
            "diagnostic_subtype": str(diagnostic.get("error_subtype") or ""),
            "planned_actions": plan.get("actions_ir") if isinstance(plan.get("actions_ir"), list) else [],
            "applied_actions": [],
            "hard_check_result": False,
            "next_failure_type": "",
            "plan_error_code": str(plan.get("plan_error_code") or ""),
            "apply_error_code": "",
        }
        if plan.get("status") != "PASS":
            trajectory_row["apply_error_code"] = str(plan.get("plan_error_code") or "action_plan_invalid")
            trajectory_rows.append(trajectory_row)
            stop_reason = "action_plan_failed"
            break

        apply_result = apply_repair_actions_to_modelica_v0(
            modelica_text=current_text,
            actions_payload=[x for x in (plan.get("actions_ir") or []) if isinstance(x, dict)],
            max_actions_per_round=max(1, int(max_actions_per_round)),
            allowed_component_types=DEFAULT_COMPONENT_WHITELIST,
        )
        if apply_result.get("status") != "PASS":
            trajectory_row["apply_error_code"] = str(apply_result.get("apply_error_code") or "apply_failed")
            trajectory_rows.append(trajectory_row)
            # rollback: keep current_text as-is and try next round unless guard stops.
            current_actions = [str(x) for x in (plan.get("actions_text") or []) if isinstance(x, str)]
            continue

        trajectory_row["applied_actions"] = [x for x in (apply_result.get("applied_actions") or []) if isinstance(x, dict)]
        trajectory_rows.append(trajectory_row)
        current_text = str(apply_result.get("updated_modelica_text") or current_text)
        current_actions = [str(x) for x in (plan.get("actions_text") or []) if isinstance(x, str)]

    for idx, row in enumerate(trajectory_rows):
        if idx + 1 < len(attempts):
            row["next_failure_type"] = str(attempts[idx + 1].get("observed_failure_type") or "")
        elif attempts:
            row["next_failure_type"] = str(attempts[-1].get("observed_failure_type") or "")

    for idx, attempt in enumerate(attempts):
        step = trajectory_rows[idx] if idx < len(trajectory_rows) and isinstance(trajectory_rows[idx], dict) else {}
        attempt["l4"] = {
            "planned_actions": step.get("planned_actions") if isinstance(step.get("planned_actions"), list) else [],
            "applied_actions": step.get("applied_actions") if isinstance(step.get("applied_actions"), list) else [],
            "plan_error_code": str(step.get("plan_error_code") or ""),
            "apply_error_code": str(step.get("apply_error_code") or ""),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "rounds_used": rounds_used,
        "elapsed_sec": round(elapsed_total, 4),
        "hard_checks": hard_checks,
        "stop_reason": stop_reason,
        "attempts": attempts,
        "trajectory_rows": trajectory_rows,
        "action_effectiveness": summarize_action_effectiveness_v2(trajectory_rows),
        "final_model_text": current_text,
        "policy_backend": str(policy_backend or "rule"),
    }


def to_jsonable_summary(orchestrator_payload: dict) -> str:
    payload = orchestrator_payload if isinstance(orchestrator_payload, dict) else {}
    return json.dumps(
        {
            "status": payload.get("status"),
            "passed": payload.get("passed"),
            "rounds_used": payload.get("rounds_used"),
            "elapsed_sec": payload.get("elapsed_sec"),
            "stop_reason": payload.get("stop_reason"),
            "trajectory_rows": len(payload.get("trajectory_rows") or []),
        },
        ensure_ascii=True,
    )
