from __future__ import annotations

import json
import re
import statistics
from typing import Callable

from .agent_modelica_action_applier_v0 import apply_repair_actions_to_modelica_v0
from .agent_modelica_diagnostic_ir_v0 import build_diagnostic_ir_v0
from .agent_modelica_error_action_mapper_v1 import map_error_to_actions
from .agent_modelica_modeling_ir_v0 import DEFAULT_COMPONENT_WHITELIST, modelica_to_ir
from .agent_modelica_orchestrator_guard_v0 import detect_no_progress_v0, prioritize_repair_actions_v0
from .agent_modelica_l4_policy_profile_v0 import DEFAULT_POLICY_PROFILE, resolve_l4_policy_profile_v0
from .agent_modelica_repair_action_ir_v0 import validate_action_batch_v0
from .agent_modelica_repair_action_policy_v0 import recommend_repair_actions_v0
from .agent_modelica_repair_memory_v2 import summarize_action_effectiveness_v2
from .agent_modelica_retrieval_augmented_repair_v1 import retrieve_repair_examples


SCHEMA_VERSION = "agent_modelica_l4_orchestrator_v0"
ALLOWED_L4_PRIMARY_REASONS = {
    "hard_checks_pass",
    "max_rounds_reached",
    "time_budget_exceeded",
    "no_progress_window",
    "action_plan_failed",
    "apply_failed",
    "llm_fallback_exhausted",
}
INFRA_FAILURE_TYPES = {
    "executor_invocation_error",
    "executor_runtime_error",
    "live_executor_timeout",
    "timeout",
    "path_not_found",
    "mount_permission_denied",
    "docker_permission_denied",
}


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


def _normalize_signature_fragment(value: object) -> str:
    if isinstance(value, dict):
        return json.dumps({str(k): value[k] for k in sorted(value.keys())}, ensure_ascii=True, sort_keys=True)
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _action_signature(action: dict) -> str:
    op = str(action.get("op") or "").strip()
    target = action.get("target") if isinstance(action.get("target"), dict) else {}
    args = action.get("args") if isinstance(action.get("args"), dict) else {}
    key_args: dict[str, object] = {}
    for key in ("value", "new_type", "from", "to"):
        if key in args:
            key_args[key] = args[key]
    if "value" not in key_args and "value" in target:
        key_args["value"] = target.get("value")
    return "|".join(
        [
            f"op={op}",
            f"target={_normalize_signature_fragment(target)}",
            f"key_args={_normalize_signature_fragment(key_args)}",
        ]
    )


def _iter_memory_rows(payload: dict) -> list[dict]:
    rows: list[dict] = []
    if not isinstance(payload, dict):
        return rows

    direct_rows = payload.get("trajectory_rows") if isinstance(payload.get("trajectory_rows"), list) else []
    for row in direct_rows:
        if isinstance(row, dict):
            rows.append(row)

    legacy_rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    for row in legacy_rows:
        if isinstance(row, dict) and (
            isinstance(row.get("planned_actions"), list) or isinstance(row.get("applied_actions"), list)
        ):
            rows.append(row)

    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        attempts = rec.get("attempts") if isinstance(rec.get("attempts"), list) else []
        for idx, attempt in enumerate([x for x in attempts if isinstance(x, dict)]):
            l4 = attempt.get("l4") if isinstance(attempt.get("l4"), dict) else {}
            diag = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
            next_failure_type = ""
            if idx + 1 < len(attempts) and isinstance(attempts[idx + 1], dict):
                next_failure_type = str(attempts[idx + 1].get("observed_failure_type") or "")
            rows.append(
                {
                    "task_id": str(rec.get("task_id") or ""),
                    "round": int(attempt.get("round") or idx + 1),
                    "diagnostic_subtype": str(diag.get("error_subtype") or ""),
                    "planned_actions": l4.get("planned_actions") if isinstance(l4.get("planned_actions"), list) else [],
                    "applied_actions": l4.get("applied_actions") if isinstance(l4.get("applied_actions"), list) else [],
                    "hard_check_result": bool(
                        bool(attempt.get("check_model_pass"))
                        and bool(attempt.get("simulate_pass"))
                        and bool(attempt.get("physics_contract_pass"))
                        and bool(attempt.get("regression_pass"))
                    ),
                    "next_failure_type": next_failure_type,
                }
            )
    return rows


def _build_memory_feature_index(repair_history_payload: dict, current_rows: list[dict]) -> dict:
    joined_rows = _iter_memory_rows(repair_history_payload) + [x for x in current_rows if isinstance(x, dict)]
    by_key: dict[tuple[str, str], dict] = {}
    by_sig: dict[str, dict] = {}

    def _touch(slot: dict, *, hard_ok: bool, row_round: int, infra_risk: bool) -> None:
        slot["count"] = int(slot.get("count", 0) or 0) + 1
        if hard_ok:
            slot["success_count"] = int(slot.get("success_count", 0) or 0) + 1
            rounds = slot.get("pass_rounds") if isinstance(slot.get("pass_rounds"), list) else []
            rounds.append(int(max(1, row_round)))
            slot["pass_rounds"] = rounds
        if infra_risk:
            slot["infra_count"] = int(slot.get("infra_count", 0) or 0) + 1

    for row in joined_rows:
        subtype = str(row.get("diagnostic_subtype") or "").strip().lower()
        hard_ok = bool(row.get("hard_check_result"))
        row_round = int(row.get("round") or 1)
        next_failure_type = str(row.get("next_failure_type") or "").strip().lower()
        infra_risk = next_failure_type in INFRA_FAILURE_TYPES
        actions = []
        if isinstance(row.get("applied_actions"), list):
            actions.extend([x for x in row.get("applied_actions") if isinstance(x, dict)])
        if isinstance(row.get("planned_actions"), list):
            actions.extend([x for x in row.get("planned_actions") if isinstance(x, dict)])
        for action in actions:
            sig = _action_signature(action)
            key = (subtype, sig)
            slot = by_key.setdefault(key, {"count": 0, "success_count": 0, "infra_count": 0, "pass_rounds": []})
            _touch(slot, hard_ok=hard_ok, row_round=row_round, infra_risk=infra_risk)
            sig_slot = by_sig.setdefault(sig, {"count": 0, "success_count": 0, "infra_count": 0, "pass_rounds": []})
            _touch(sig_slot, hard_ok=hard_ok, row_round=row_round, infra_risk=infra_risk)

    return {"by_key": by_key, "by_sig": by_sig}


def _memory_features(index: dict, diagnostic_subtype: str, signature: str) -> dict:
    subtype = str(diagnostic_subtype or "").strip().lower()
    by_key = index.get("by_key") if isinstance(index.get("by_key"), dict) else {}
    by_sig = index.get("by_sig") if isinstance(index.get("by_sig"), dict) else {}
    slot = by_key.get((subtype, signature)) if isinstance(by_key, dict) else None
    if not isinstance(slot, dict):
        slot = by_sig.get(signature) if isinstance(by_sig, dict) else None
    if not isinstance(slot, dict):
        return {
            "success_rate": 0.0,
            "median_round_to_pass": 0.0,
            "infra_risk_rate": 0.0,
            "seen_count": 0,
        }
    count = int(slot.get("count", 0) or 0)
    success_count = int(slot.get("success_count", 0) or 0)
    infra_count = int(slot.get("infra_count", 0) or 0)
    pass_rounds = [int(x) for x in (slot.get("pass_rounds") or []) if isinstance(x, int)]
    return {
        "success_rate": round((success_count / count), 4) if count > 0 else 0.0,
        "median_round_to_pass": round(float(statistics.median(pass_rounds)), 2) if pass_rounds else 0.0,
        "infra_risk_rate": round((infra_count / count), 4) if count > 0 else 0.0,
        "seen_count": count,
    }


def _stage_match_score(expected_stage: str, op: str) -> int:
    stage = str(expected_stage or "").strip().lower()
    operation = str(op or "").strip().lower()
    if stage == "check":
        if operation in {"connect_ports", "disconnect_ports", "replace_component"}:
            return 3
        if operation in {"set_parameter", "set_start_value"}:
            return 1
        return 0
    if stage == "simulate":
        if operation in {"set_parameter", "set_start_value"}:
            return 3
        if operation in {"connect_ports", "disconnect_ports"}:
            return 2
        if operation in {"replace_component"}:
            return 1
        return 0
    return 1


def _subtype_match_score(error_subtype: str, op: str, action_text: str) -> int:
    subtype = str(error_subtype or "").strip().lower()
    operation = str(op or "").strip().lower()
    text = str(action_text or "").strip().lower()
    if any(k in subtype for k in ("parse", "undefined", "connector", "mismatch")):
        if operation in {"connect_ports", "disconnect_ports", "replace_component"}:
            return 3
        if operation in {"set_parameter"}:
            return 1
    if any(k in subtype for k in ("init", "solver", "assertion", "numerical", "timeout")):
        if operation in {"set_start_value", "set_parameter"}:
            return 3
        if operation in {"replace_component"}:
            return 1
    if "semantic" in subtype:
        if operation in {"set_parameter", "replace_component"}:
            return 2
    if "connector" in text and operation in {"connect_ports", "disconnect_ports"}:
        return 2
    if "replace" in text and operation == "replace_component":
        return 2
    return 1


def _phase_priority(recovery_stage: int, op: str) -> int:
    stage = max(1, min(3, int(recovery_stage)))
    operation = str(op or "").strip().lower()
    if stage == 1:
        if operation in {"set_parameter", "set_start_value"}:
            return 3
        if operation in {"connect_ports", "disconnect_ports"}:
            return 2
        if operation == "replace_component":
            return 1
        return 0
    if stage == 2:
        if operation in {"connect_ports", "disconnect_ports"}:
            return 3
        if operation in {"set_parameter", "set_start_value"}:
            return 2
        if operation == "replace_component":
            return 1
        return 0
    if operation == "replace_component":
        return 3
    if operation in {"connect_ports", "disconnect_ports"}:
        return 2
    if operation in {"set_parameter", "set_start_value"}:
        return 1
    return 0


def _llm_fallback_seed_actions(
    *,
    diagnostic_payload: dict,
    merged_actions: list[str],
    mapped_actions: list[str],
    fallback_actions: list[str],
) -> list[str]:
    out = _merge_actions(
        [str(x) for x in (fallback_actions or []) if isinstance(x, str)],
        [str(x) for x in (merged_actions or []) if isinstance(x, str)],
        [str(x) for x in (mapped_actions or []) if isinstance(x, str)],
        [str(x) for x in (diagnostic_payload.get("suggested_actions") or []) if isinstance(x, str)],
    )
    subtype = str(diagnostic_payload.get("error_subtype") or "").lower()
    if not out:
        if "connector" in subtype or "parse" in subtype:
            out.append("fix connector type/causality mismatch")
        elif "init" in subtype or "solver" in subtype or "numerical" in subtype:
            out.append("stabilize initialization and start values")
        else:
            out.append("scan undefined symbols and missing declarations")
    return out


def _normalize_l4_primary_reason(stop_reason: str, passed: bool) -> str:
    if bool(passed):
        return "hard_checks_pass"
    text = str(stop_reason or "").strip()
    if text in ALLOWED_L4_PRIMARY_REASONS:
        return text
    return "action_plan_failed"


def build_l4_action_plan_v0(
    *,
    task: dict,
    diagnostic_payload: dict,
    modelica_text: str,
    fallback_actions: list[str],
    repair_history_payload: dict,
    retrieval_policy_payload: dict,
    policy_backend: str,
    policy_profile: str,
    max_actions_per_round: int,
    recovery_stage: int,
    attempted_signature_counts: dict[str, int],
    banned_action_signatures: set[str],
    no_progress_strikes: int,
    llm_fallback_threshold: int,
    recent_ops: set[str],
    trajectory_rows: list[dict],
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
    policy_actions = [str(x) for x in (policy.get("actions") or []) if isinstance(x, str)]
    mapped_actions = [str(x) for x in (mapped.get("actions") or []) if isinstance(x, str)]
    retrieved_actions = [str(x) for x in (retrieved.get("suggested_actions") or []) if isinstance(x, str)]
    merged_actions = _merge_actions(policy_actions, mapped_actions, retrieved_actions, [str(x) for x in (fallback_actions or []) if isinstance(x, str)])
    ordered_actions = prioritize_repair_actions_v0(merged_actions, expected_stage=expected_stage)

    try:
        ir_payload = modelica_to_ir(str(modelica_text or ""))
    except Exception as exc:
        return {
            "status": "FAIL",
            "plan_error_code": "modelica_to_ir_failed",
            "errors": [str(exc)],
            "actions_text": [],
            "actions_ir": [],
            "action_rank_trace": [],
            "selected_signatures": [],
            "llm_fallback_used": False,
        }

    memory_index = _build_memory_feature_index(
        repair_history_payload if isinstance(repair_history_payload, dict) else {},
        trajectory_rows if isinstance(trajectory_rows, list) else [],
    )
    policy_profile_cfg = resolve_l4_policy_profile_v0(str(policy_profile or DEFAULT_POLICY_PROFILE))
    score_weights = policy_profile_cfg.get("score_weights") if isinstance(policy_profile_cfg.get("score_weights"), dict) else {}
    memory_terms = policy_profile_cfg.get("memory_terms") if isinstance(policy_profile_cfg.get("memory_terms"), dict) else {}

    candidates: list[dict] = []
    seen_signatures_in_round: set[str] = set()
    debug_rows: list[dict] = []

    def _append_candidates(text_rows: list[str], *, source: str, channel: str, confidence: float) -> None:
        for idx, text in enumerate(text_rows, start=1):
            action = _build_rule_action_from_text(
                action_id=f"l4_{source}_{channel}_{idx}",
                action_text=text,
                ir_payload=ir_payload,
                source=source,
                confidence=confidence,
            )
            if not isinstance(action, dict):
                continue
            signature = _action_signature(action)
            if signature in seen_signatures_in_round:
                continue
            seen_signatures_in_round.add(signature)
            operation = str(action.get("op") or "").strip().lower()
            stage_match = _stage_match_score(expected_stage=expected_stage, op=operation)
            subtype_match = _subtype_match_score(
                error_subtype=str(diagnostic_payload.get("error_subtype") or ""),
                op=operation,
                action_text=text,
            )
            phase_match = _phase_priority(recovery_stage=recovery_stage, op=operation)
            memory = _memory_features(
                memory_index,
                diagnostic_subtype=str(diagnostic_payload.get("error_subtype") or ""),
                signature=signature,
            )
            retrieval_support = 1 if channel == "retrieval" else 0
            retry_penalty = int(attempted_signature_counts.get(signature, 0) or 0)
            diversity_bonus = 1 if operation not in recent_ops else 0

            memory_effectiveness = round(
                float(memory.get("success_rate", 0.0)) * float(memory_terms.get("success_scale", 20.0))
                - float(memory.get("infra_risk_rate", 0.0)) * float(memory_terms.get("infra_risk_scale", 12.0))
                - max(0.0, float(memory.get("median_round_to_pass", 0.0)) - 1.0) * float(memory_terms.get("round_penalty", 1.5)),
                3,
            )
            score = round(
                phase_match * float(score_weights.get("phase", 1000.0))
                + stage_match * float(score_weights.get("stage", 220.0))
                + subtype_match * float(score_weights.get("subtype", 140.0))
                + memory_effectiveness * float(score_weights.get("memory", 8.0))
                + retrieval_support * float(score_weights.get("retrieval", 20.0))
                - retry_penalty * float(score_weights.get("retry_penalty", 80.0))
                + diversity_bonus * float(score_weights.get("diversity", 8.0)),
                3,
            )
            banned = signature in banned_action_signatures
            candidate_row = {
                "text": str(text),
                "action": action,
                "signature": signature,
                "op": operation,
                "source": source,
                "channel": channel,
                "banned": bool(banned),
                "score": score,
                "score_terms": {
                    "phase_match": phase_match,
                    "stage_match": stage_match,
                    "subtype_match": subtype_match,
                    "memory_effectiveness": memory_effectiveness,
                    "memory_success_rate": float(memory.get("success_rate", 0.0)),
                    "memory_median_round_to_pass": float(memory.get("median_round_to_pass", 0.0)),
                    "memory_infra_risk_rate": float(memory.get("infra_risk_rate", 0.0)),
                    "memory_seen_count": int(memory.get("seen_count", 0) or 0),
                    "retrieval_support": retrieval_support,
                    "retry_penalty": retry_penalty,
                    "diversity_bonus": diversity_bonus,
                },
            }
            candidates.append(candidate_row)
            debug_rows.append(
                {
                    "signature": signature,
                    "op": operation,
                    "source": source,
                    "channel": channel,
                    "banned": bool(banned),
                    "score": score,
                    "score_terms": candidate_row["score_terms"],
                }
            )

    _append_candidates(policy_actions, source="rule", channel="policy", confidence=0.74)
    _append_candidates(mapped_actions, source="rule", channel="mapped", confidence=0.72)
    _append_candidates(retrieved_actions, source="rule", channel="retrieval", confidence=0.71)
    _append_candidates(ordered_actions, source="rule", channel="merged", confidence=0.7)

    candidates.sort(
        key=lambda row: (
            -float(row.get("score", 0.0)),
            -int(((row.get("score_terms") or {}).get("stage_match") or 0)),
            -int(((row.get("score_terms") or {}).get("subtype_match") or 0)),
            -int(((row.get("score_terms") or {}).get("memory_seen_count") or 0)),
            str(row.get("signature") or ""),
        )
    )

    selected_candidates = [row for row in candidates if not bool(row.get("banned"))][: max(1, int(max_actions_per_round))]
    llm_fallback_used = False
    llm_fallback_exhausted = False

    rules_empty = len(candidates) == 0
    no_exec_due_to_blacklist = len(candidates) > 0 and len(selected_candidates) == 0
    should_trigger_llm = (
        str(policy_backend or "").strip().lower() == "llm"
        and (rules_empty or (int(no_progress_strikes) >= int(max(1, llm_fallback_threshold)) and no_exec_due_to_blacklist))
    )

    if should_trigger_llm:
        llm_fallback_used = True
        llm_seed = _llm_fallback_seed_actions(
            diagnostic_payload=diagnostic_payload,
            merged_actions=merged_actions,
            mapped_actions=mapped_actions,
            fallback_actions=[str(x) for x in (fallback_actions or []) if isinstance(x, str)],
        )
        _append_candidates(llm_seed, source="llm", channel="llm_fallback", confidence=0.62)
        candidates.sort(
            key=lambda row: (
                -float(row.get("score", 0.0)),
                -int(((row.get("score_terms") or {}).get("stage_match") or 0)),
                -int(((row.get("score_terms") or {}).get("subtype_match") or 0)),
                -int(((row.get("score_terms") or {}).get("memory_seen_count") or 0)),
                str(row.get("signature") or ""),
            )
        )
        selected_candidates = [row for row in candidates if not bool(row.get("banned"))][: max(1, int(max_actions_per_round))]
        if not selected_candidates:
            llm_fallback_exhausted = True

    selected_actions_raw = [row.get("action") for row in selected_candidates if isinstance(row.get("action"), dict)]
    selected_actions_raw = [x for x in selected_actions_raw if isinstance(x, dict)]

    validation = validate_action_batch_v0(
        actions_payload=selected_actions_raw,
        ir_payload=ir_payload,
        max_actions_per_round=max(1, int(max_actions_per_round)),
        allowed_component_types=DEFAULT_COMPONENT_WHITELIST,
    )
    normalized = validation.get("normalized_actions") if isinstance(validation.get("normalized_actions"), list) else []
    selected_signatures = [_action_signature(x) for x in normalized if isinstance(x, dict)]
    selected_text_actions = [str(row.get("text") or "") for row in selected_candidates if isinstance(row, dict)]

    plan_error_code = ""
    status = "PASS"
    if llm_fallback_exhausted:
        plan_error_code = "llm_fallback_exhausted"
        status = "FAIL"
    elif validation.get("status") != "PASS" or not normalized:
        plan_error_code = "action_plan_invalid"
        status = "FAIL"

    return {
        "status": status,
        "plan_error_code": plan_error_code,
        "errors": list(validation.get("errors") or []),
        "rejected_actions": list(validation.get("rejected_actions") or []),
        "actions_text": selected_text_actions,
        "actions_ir": normalized,
        "selected_signatures": selected_signatures,
        "policy_channel": str(policy.get("channel") or ""),
        "retrieved_count": int(retrieved.get("retrieved_count", 0) or 0),
        "action_rank_trace": debug_rows,
        "llm_fallback_used": llm_fallback_used,
        "llm_fallback_exhausted": llm_fallback_exhausted,
        "recovery_stage": int(max(1, min(3, int(recovery_stage)))),
        "policy_profile": str(policy_profile_cfg.get("resolved_profile") or DEFAULT_POLICY_PROFILE),
        "policy_profile_requested": str(policy_profile_cfg.get("requested_profile") or ""),
        "policy_profile_fallback_used": bool(policy_profile_cfg.get("fallback_used")),
        "policy_profile_score_weights": score_weights,
        "policy_profile_memory_terms": memory_terms,
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
    policy_profile: str = DEFAULT_POLICY_PROFILE,
    llm_fallback_threshold: int = 2,
    repair_history_payload: dict | None = None,
    retrieval_policy_payload: dict | None = None,
) -> dict:
    rounds = max(1, int(max_rounds))
    time_budget = max(1, int(max_time_sec))
    current_text = str(initial_model_text or "")
    current_actions = [str(x) for x in (initial_actions or []) if isinstance(x, str)]

    attempts: list[dict] = []
    trajectory_rows: list[dict] = []
    action_rank_trace: list[dict] = []
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

    attempted_signature_counts: dict[str, int] = {}
    banned_action_signatures: set[str] = set()
    recent_ops: set[str] = set()
    no_progress_strikes = 0
    previous_subtype = ""
    previous_attempted_signatures: list[str] = []
    llm_fallback_used = False

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

        no_progress = detect_no_progress_v0(attempts, window=max(2, int(no_progress_window)))
        if no_progress:
            no_progress_strikes += 1
        else:
            no_progress_strikes = 0

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

        current_subtype = str(diagnostic.get("error_subtype") or "").strip().lower()
        if current_subtype and previous_subtype and current_subtype == previous_subtype:
            for sig in previous_attempted_signatures:
                if sig:
                    banned_action_signatures.add(sig)

        if no_progress_strikes >= 3:
            stop_reason = "no_progress_window"
            break

        recovery_stage = 1 + int(no_progress_strikes)

        plan = build_l4_action_plan_v0(
            task=task,
            diagnostic_payload=diagnostic,
            modelica_text=current_text,
            fallback_actions=current_actions,
            repair_history_payload=repair_history_payload if isinstance(repair_history_payload, dict) else {},
            retrieval_policy_payload=retrieval_policy_payload if isinstance(retrieval_policy_payload, dict) else {},
            policy_backend=str(policy_backend or "rule"),
            policy_profile=str(policy_profile or DEFAULT_POLICY_PROFILE),
            max_actions_per_round=max(1, int(max_actions_per_round)),
            recovery_stage=max(1, min(3, int(recovery_stage))),
            attempted_signature_counts=attempted_signature_counts,
            banned_action_signatures=set(banned_action_signatures),
            no_progress_strikes=int(no_progress_strikes),
            llm_fallback_threshold=max(1, int(llm_fallback_threshold)),
            recent_ops=set(recent_ops),
            trajectory_rows=trajectory_rows,
        )
        llm_fallback_used = bool(llm_fallback_used or bool(plan.get("llm_fallback_used")))

        selected_signatures = [str(x) for x in (plan.get("selected_signatures") or []) if isinstance(x, str)]
        for sig in selected_signatures:
            attempted_signature_counts[sig] = int(attempted_signature_counts.get(sig, 0) or 0) + 1

        action_rank_trace.append(
            {
                "round": round_idx,
                "diagnostic_subtype": current_subtype,
                "recovery_stage": int(plan.get("recovery_stage") or max(1, min(3, int(recovery_stage)))),
                "policy_profile": str(plan.get("policy_profile") or policy_profile or DEFAULT_POLICY_PROFILE),
                "llm_fallback_used": bool(plan.get("llm_fallback_used")),
                "selected_signatures": selected_signatures,
                "candidates": [x for x in (plan.get("action_rank_trace") or []) if isinstance(x, dict)],
            }
        )

        trajectory_row = {
            "task_id": str(task.get("task_id") or ""),
            "round": round_idx,
            "diagnostic_subtype": current_subtype,
            "planned_actions": plan.get("actions_ir") if isinstance(plan.get("actions_ir"), list) else [],
            "applied_actions": [],
            "hard_check_result": False,
            "next_failure_type": "",
            "plan_error_code": str(plan.get("plan_error_code") or ""),
            "apply_error_code": "",
            "policy_profile": str(plan.get("policy_profile") or policy_profile or DEFAULT_POLICY_PROFILE),
            "recovery_stage": int(plan.get("recovery_stage") or max(1, min(3, int(recovery_stage)))),
            "llm_fallback_used": bool(plan.get("llm_fallback_used")),
            "selected_signatures": selected_signatures,
        }

        if plan.get("status") != "PASS":
            trajectory_row["apply_error_code"] = str(plan.get("plan_error_code") or "action_plan_invalid")
            trajectory_rows.append(trajectory_row)
            if str(plan.get("plan_error_code") or "") == "llm_fallback_exhausted":
                stop_reason = "llm_fallback_exhausted"
            else:
                stop_reason = "action_plan_failed"
            previous_subtype = current_subtype
            previous_attempted_signatures = selected_signatures
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
            current_actions = [str(x) for x in (plan.get("actions_text") or []) if isinstance(x, str)]
            previous_subtype = current_subtype
            previous_attempted_signatures = selected_signatures
            if no_progress_strikes >= 2 and str(policy_backend or "").strip().lower() != "llm":
                stop_reason = "apply_failed"
                break
            continue

        trajectory_row["applied_actions"] = [x for x in (apply_result.get("applied_actions") or []) if isinstance(x, dict)]
        for action in trajectory_row["applied_actions"]:
            recent_ops.add(str(action.get("op") or "").strip().lower())
        trajectory_rows.append(trajectory_row)
        current_text = str(apply_result.get("updated_modelica_text") or current_text)
        current_actions = [str(x) for x in (plan.get("actions_text") or []) if isinstance(x, str)]
        previous_subtype = current_subtype
        previous_attempted_signatures = selected_signatures

    for idx, row in enumerate(trajectory_rows):
        if idx + 1 < len(attempts):
            next_attempt = attempts[idx + 1] if isinstance(attempts[idx + 1], dict) else {}
            row["next_failure_type"] = str(next_attempt.get("observed_failure_type") or "")
            row["hard_check_result"] = bool(
                bool(next_attempt.get("check_model_pass"))
                and bool(next_attempt.get("simulate_pass"))
                and bool(next_attempt.get("physics_contract_pass"))
                and bool(next_attempt.get("regression_pass"))
            )
        elif attempts:
            row["next_failure_type"] = str(attempts[-1].get("observed_failure_type") or "")

    for idx, attempt in enumerate(attempts):
        step = trajectory_rows[idx] if idx < len(trajectory_rows) and isinstance(trajectory_rows[idx], dict) else {}
        attempt["l4"] = {
            "planned_actions": step.get("planned_actions") if isinstance(step.get("planned_actions"), list) else [],
            "applied_actions": step.get("applied_actions") if isinstance(step.get("applied_actions"), list) else [],
            "plan_error_code": str(step.get("plan_error_code") or ""),
            "apply_error_code": str(step.get("apply_error_code") or ""),
            "selected_signatures": [str(x) for x in (step.get("selected_signatures") or []) if isinstance(x, str)],
            "llm_fallback_used": bool(step.get("llm_fallback_used")),
            "recovery_stage": int(step.get("recovery_stage") or 1),
        }

    l4_primary_reason = _normalize_l4_primary_reason(stop_reason=stop_reason, passed=passed)
    if (not passed) and l4_primary_reason == "action_plan_failed" and stop_reason == "apply_failed":
        l4_primary_reason = "apply_failed"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "rounds_used": rounds_used,
        "elapsed_sec": round(elapsed_total, 4),
        "hard_checks": hard_checks,
        "stop_reason": stop_reason,
        "l4_primary_reason": l4_primary_reason,
        "attempts": attempts,
        "trajectory_rows": trajectory_rows,
        "action_effectiveness": summarize_action_effectiveness_v2(trajectory_rows),
        "action_rank_trace": action_rank_trace,
        "banned_action_signatures": sorted([x for x in banned_action_signatures if x]),
        "llm_fallback_used": bool(llm_fallback_used),
        "reason_enum": sorted(ALLOWED_L4_PRIMARY_REASONS),
        "final_model_text": current_text,
        "policy_backend": str(policy_backend or "rule"),
        "policy_profile": str(policy_profile or DEFAULT_POLICY_PROFILE),
        "llm_fallback_threshold": max(1, int(llm_fallback_threshold)),
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
            "l4_primary_reason": payload.get("l4_primary_reason"),
            "llm_fallback_used": payload.get("llm_fallback_used"),
            "trajectory_rows": len(payload.get("trajectory_rows") or []),
        },
        ensure_ascii=True,
    )
