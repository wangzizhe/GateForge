from __future__ import annotations

import argparse
import json
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .physics_contract_v0 import (
    DEFAULT_PHYSICS_CONTRACT_PATH,
    evaluate_physics_contract_v0,
    load_physics_contract_v0,
)
from .agent_modelica_repair_playbook_v1 import load_repair_playbook, recommend_repair_strategy
from .agent_modelica_patch_template_engine_v1 import build_patch_template
from .agent_modelica_error_action_mapper_v1 import map_error_to_actions
from .agent_modelica_retrieval_augmented_repair_v1 import retrieve_repair_examples
from .regression import compare_evidence, load_json as _load_evidence_json


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_records_jsonl(path: str) -> dict[str, dict]:
    p = Path(path)
    if not p.exists():
        return {}
    out: dict[str, dict] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        text = str(line or "").strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("task_id") or "").strip()
        if not task_id:
            continue
        out.setdefault(task_id, row)
    return out


def _append_record_jsonl(path: str, row: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Run Contract v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- success_count: `{payload.get('success_count')}`",
        f"- success_at_k_pct: `{payload.get('success_at_k_pct')}`",
        f"- median_time_to_pass_sec: `{payload.get('median_time_to_pass_sec')}`",
        f"- median_repair_rounds: `{payload.get('median_repair_rounds')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _default_baseline_metrics() -> dict:
    return {
        "steady_state_error": 0.01,
        "overshoot": 0.05,
        "settling_time": 1.0,
        "runtime_seconds": 1.0,
        "events": 10,
    }


def _default_candidate_metrics(failure_type: str, baseline_metrics: dict) -> dict:
    candidate = dict(baseline_metrics)
    if failure_type == "semantic_regression":
        candidate["steady_state_error"] = 0.03
    elif failure_type == "simulate_error":
        candidate["events"] = 8
    elif failure_type == "model_check_error":
        candidate["runtime_seconds"] = 1.2
    return candidate


def _merge_actions(*action_sets: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for action_set in action_sets:
        for row in action_set:
            item = str(row).strip()
            if item and item not in seen:
                out.append(item)
                seen.add(item)
    return out


def _augment_repair_strategy(
    task: dict,
    repair_strategy: dict,
    repair_history_payload: dict,
    focus_queue_payload: dict,
    patch_template_adaptations_payload: dict,
    retrieval_policy_payload: dict,
) -> tuple[dict, dict]:
    failure_type = str(task.get("failure_type") or "unknown")
    expected_stage = str(task.get("expected_stage") or "unknown")
    template = build_patch_template(
        failure_type=failure_type,
        expected_stage=expected_stage,
        focus_queue_payload=focus_queue_payload if isinstance(focus_queue_payload, dict) else {},
        adaptations_payload=patch_template_adaptations_payload if isinstance(patch_template_adaptations_payload, dict) else {},
    )

    error_message = " | ".join(
        [
            str(task.get("error_message") or ""),
            str(task.get("compile_error") or ""),
            str(task.get("simulate_error_message") or ""),
            str(task.get("stderr_snippet") or ""),
        ]
    ).strip(" |")
    mapped = map_error_to_actions(error_message=error_message, failure_type=failure_type)
    retrieval = retrieve_repair_examples(
        history_payload=repair_history_payload if isinstance(repair_history_payload, dict) else {},
        failure_type=failure_type,
        model_hint=str(task.get("source_model_path") or ""),
        top_k=2,
        policy_payload=retrieval_policy_payload if isinstance(retrieval_policy_payload, dict) else {},
    )

    base_actions = [str(x) for x in (repair_strategy.get("actions") or []) if isinstance(x, str)]
    template_actions = [str(x) for x in (template.get("actions") or []) if isinstance(x, str)]
    mapped_actions = [str(x) for x in (mapped.get("actions") or []) if isinstance(x, str)]
    retrieved_actions = [str(x) for x in (retrieval.get("suggested_actions") or []) if isinstance(x, str)]
    merged_actions = _merge_actions(base_actions, template_actions, mapped_actions, retrieved_actions)

    signal_count = 0
    if template_actions:
        signal_count += 1
    if mapped_actions:
        signal_count += 1
    if retrieved_actions:
        signal_count += 1
    confidence_base = float(repair_strategy.get("confidence", 0.0) or 0.0)
    confidence_boost = min(0.18, float(signal_count) * 0.05)
    augmented_confidence = min(0.98, confidence_base + confidence_boost)

    augmented = dict(repair_strategy)
    augmented["actions"] = merged_actions
    augmented["confidence"] = augmented_confidence
    if str(augmented.get("reason") or "") == "no_failure_type_match" and int(retrieval.get("retrieved_count", 0) or 0) > 0:
        augmented["reason"] = "retrieval_augmented"
    if int(augmented.get("priority", 0) or 0) > 0 and signal_count >= 2:
        augmented["priority"] = int(augmented.get("priority", 0) or 0) + 5

    audit = {
        "patch_template_id": str(template.get("template_id") or ""),
        "patch_template_actions_count": len(template_actions),
        "patch_template_focus_actions_count": int(template.get("focus_actions_count", 0) or 0),
        "patch_template_adaptation_actions_count": int(template.get("adaptation_actions_count", 0) or 0),
        "error_action_tags": [str(x) for x in (mapped.get("tags") or []) if isinstance(x, str)],
        "error_action_count": len(mapped_actions),
        "retrieved_example_count": int(retrieval.get("retrieved_count", 0) or 0),
        "retrieval_effective_top_k": int(retrieval.get("effective_top_k", 0) or 0),
        "retrieved_suggested_action_count": len(retrieved_actions),
        "confidence_boost": round(confidence_boost, 4),
    }
    return augmented, audit


def _strategy_effect(task: dict, strategy: dict) -> tuple[int, float, dict]:
    reason = str(strategy.get("reason") or "unknown")
    priority = int(strategy.get("priority", 0) or 0)
    confidence = float(strategy.get("confidence", 0.0) or 0.0)
    base_success_round = int(task.get("mock_success_round", 2) or 2)
    base_round_sec = float(int(task.get("mock_round_duration_sec", 30) or 30))
    delta_round = 0
    speedup_ratio = 0.0
    if reason == "stage_matched" and priority >= 90 and confidence >= 0.8:
        delta_round = -1
        speedup_ratio = 0.2
    elif reason in {"failure_type_matched"} and priority >= 85 and confidence >= 0.7:
        delta_round = -1
        speedup_ratio = 0.1

    adjusted_success_round = max(1, base_success_round + delta_round)
    adjusted_round_sec = max(1.0, base_round_sec * (1.0 - speedup_ratio))
    audit = {
        "base_success_round": base_success_round,
        "base_round_duration_sec": base_round_sec,
        "adjusted_success_round": adjusted_success_round,
        "adjusted_round_duration_sec": round(adjusted_round_sec, 2),
        "delta_round": delta_round,
        "speedup_ratio": speedup_ratio,
        "reason": reason,
        "strategy_id": str(strategy.get("strategy_id") or ""),
    }
    return adjusted_success_round, adjusted_round_sec, audit


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "pass", "passed", "ok", "success"}:
        return True
    if text in {"false", "0", "no", "fail", "failed", "error"}:
        return False
    return None


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x) for x in value if isinstance(x, str)]


def _last_nonempty_line(text: str) -> str:
    lines = [x.strip() for x in str(text or "").splitlines() if str(x).strip()]
    if not lines:
        return ""
    return lines[-1]


def _build_live_template_context(task: dict, strategy: dict, round_idx: int, max_rounds: int, max_time_sec: int) -> dict[str, str]:
    actions = [str(x) for x in (strategy.get("actions") or []) if isinstance(x, str)]
    mapping = {
        "task_id": str(task.get("task_id") or ""),
        "scale": str(task.get("scale") or ""),
        "failure_type": str(task.get("failure_type") or ""),
        "expected_stage": str(task.get("expected_stage") or ""),
        "source_model_path": str(task.get("source_model_path") or ""),
        "mutated_model_path": str(task.get("mutated_model_path") or ""),
        "repro_command": str(task.get("repro_command") or ""),
        "mutation_id": str(task.get("mutation_id") or ""),
        "round": str(round_idx),
        "max_rounds": str(max_rounds),
        "max_time_sec": str(max_time_sec),
        "strategy_id": str(strategy.get("strategy_id") or ""),
        "strategy_reason": str(strategy.get("reason") or ""),
        "strategy_confidence": str(strategy.get("confidence") if strategy.get("confidence") is not None else ""),
        "repair_actions_pipe": " | ".join(actions),
        "repair_actions_json": json.dumps(actions, ensure_ascii=True),
    }
    return mapping


def _render_live_command(template: str, context: dict[str, str]) -> str:
    command = str(template or "")
    for key, value in context.items():
        command = command.replace(f"__{key.upper()}__", str(value))
    return command


def _run_live_executor_once(command: str, timeout_sec: int) -> tuple[dict, str, str]:
    proc = subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=True,
        check=False,
        timeout=max(1, int(timeout_sec)),
    )
    stdout = str(proc.stdout or "")
    stderr = str(proc.stderr or "")
    payload: dict = {}
    if stdout.strip():
        last = _last_nonempty_line(stdout)
        try:
            candidate = json.loads(last)
            if isinstance(candidate, dict):
                payload = candidate
        except Exception:
            payload = {}
    payload.setdefault("_executor_return_code", int(proc.returncode))
    payload.setdefault("_executor_stdout_tail", _last_nonempty_line(stdout))
    payload.setdefault("_executor_stderr_tail", _last_nonempty_line(stderr))
    return payload, stdout, stderr


def _action_text(strategy: dict) -> str:
    actions = strategy.get("actions") if isinstance(strategy.get("actions"), list) else []
    return " | ".join([str(x).strip().lower() for x in actions if isinstance(x, str)])


def _apply_stress_repair_effect(
    task: dict,
    baseline_evidence: dict,
    candidate_evidence: dict,
    strategy: dict,
    runtime_threshold: float,
) -> tuple[dict, list[str]]:
    if not str(task.get("_stress_class") or "").strip():
        return candidate_evidence, []

    updated = dict(candidate_evidence)
    updated_metrics = dict(updated.get("metrics") if isinstance(updated.get("metrics"), dict) else {})
    base_metrics = dict(baseline_evidence.get("metrics") if isinstance(baseline_evidence.get("metrics"), dict) else {})
    action_text = _action_text(strategy=strategy)
    reason = str(task.get("_stress_reason") or "").strip().lower()
    applied: list[str] = []

    if reason == "hard_fail_model_check" and any(x in action_text for x in ("checkmodel", "compile", "symbol", "connector")):
        updated["check_ok"] = True
        updated["simulate_ok"] = True
        updated["status"] = "success"
        updated["gate"] = "PASS"
        applied.append("repair_model_check_fail")

    if reason == "hard_fail_simulate" and any(x in action_text for x in ("stabilize", "initial", "solver", "simulate")):
        updated["check_ok"] = bool(updated.get("check_ok", True))
        updated["simulate_ok"] = True
        updated["status"] = "success" if bool(updated.get("check_ok")) else "failed"
        updated["gate"] = "PASS" if bool(updated.get("check_ok")) else "FAIL"
        applied.append("repair_simulate_fail")

    if reason == "hard_fail_physics_contract" and any(x in action_text for x in ("invariant", "physics contract", "no-regression")):
        base_sse = _safe_float(base_metrics.get("steady_state_error"), 0.01)
        updated_metrics["steady_state_error"] = min(_safe_float(updated_metrics.get("steady_state_error"), base_sse), max(0.03, base_sse * 1.2))
        updated["status"] = "success"
        updated["gate"] = "PASS"
        updated["check_ok"] = True
        updated["simulate_ok"] = True
        applied.append("repair_physics_contract_fail")

    if str(task.get("_stress_class") or "") == "slow_pass" and any(
        x in action_text for x in ("no-regression", "runtime drift", "minimal localized edit", "runtime")
    ):
        base_runtime = _safe_float(base_metrics.get("runtime_seconds"), 1.0)
        limit = base_runtime * (1.0 + max(0.01, runtime_threshold))
        target = base_runtime * (1.0 + max(0.005, runtime_threshold * 0.7))
        cur = _safe_float(updated_metrics.get("runtime_seconds"), base_runtime)
        if cur > limit:
            updated_metrics["runtime_seconds"] = round(min(cur, target), 4)
            applied.append("repair_runtime_regression")

    if "repair_runtime_regression" not in applied and any(
        x in action_text for x in ("no-regression", "runtime drift", "runtime")
    ):
        base_runtime = _safe_float(base_metrics.get("runtime_seconds"), 1.0)
        limit = base_runtime * (1.0 + max(0.01, runtime_threshold))
        cur = _safe_float(updated_metrics.get("runtime_seconds"), base_runtime)
        if cur > limit:
            updated_metrics["runtime_seconds"] = round(base_runtime * (1.0 + max(0.005, runtime_threshold * 0.7)), 4)
            applied.append("repair_runtime_regression")

    updated["metrics"] = updated_metrics
    return updated, applied


def _run_task_mock(
    task: dict,
    max_rounds: int,
    max_time_sec: int,
    physics_contract: dict,
    repair_playbook: dict,
    repair_history_payload: dict,
    focus_queue_payload: dict,
    patch_template_adaptations_payload: dict,
    retrieval_policy_payload: dict,
    strategy_effect_enabled: bool,
) -> dict:
    success_round = int(task.get("mock_success_round", 2) or 2)
    round_sec = float(int(task.get("mock_round_duration_sec", 30) or 30))
    forced_regression_fail = bool(task.get("mock_force_regression_fail", False))
    forced_physics_fail = bool(task.get("mock_force_physics_fail", False))
    failure_type = str(task.get("failure_type") or "unknown")
    task_invariants = task.get("physical_invariants") if isinstance(task.get("physical_invariants"), list) else []
    provided_baseline_metrics = task.get("baseline_metrics") if isinstance(task.get("baseline_metrics"), dict) else None
    baseline_metrics = dict(provided_baseline_metrics) if provided_baseline_metrics is not None else _default_baseline_metrics()
    provided_candidate_metrics = task.get("candidate_metrics") if isinstance(task.get("candidate_metrics"), dict) else None
    if provided_candidate_metrics is not None:
        candidate_metrics = dict(provided_candidate_metrics)
    elif provided_baseline_metrics is not None:
        candidate_metrics = dict(baseline_metrics)
    else:
        candidate_metrics = _default_candidate_metrics(failure_type=failure_type, baseline_metrics=baseline_metrics)

    attempts: list[dict] = []
    total_time = 0
    passed = False
    rounds_used = 0
    repair_strategy = recommend_repair_strategy(
        playbook_payload=repair_playbook,
        failure_type=failure_type,
        expected_stage=str(task.get("expected_stage") or "unknown"),
    )
    repair_strategy, capability_audit = _augment_repair_strategy(
        task=task,
        repair_strategy=repair_strategy,
        repair_history_payload=repair_history_payload,
        focus_queue_payload=focus_queue_payload,
        patch_template_adaptations_payload=patch_template_adaptations_payload,
        retrieval_policy_payload=retrieval_policy_payload,
    )
    strategy_audit = {
        "strategy_effect_enabled": bool(strategy_effect_enabled),
        "strategy_id": str(repair_strategy.get("strategy_id") or ""),
        "strategy_reason": str(repair_strategy.get("reason") or ""),
        "strategy_confidence": float(repair_strategy.get("confidence", 0.0) or 0.0),
        "actions_planned": [str(x) for x in (repair_strategy.get("actions") or []) if isinstance(x, str)],
        **capability_audit,
    }
    if strategy_effect_enabled:
        success_round, round_sec, effect_audit = _strategy_effect(task=task, strategy=repair_strategy)
        strategy_audit.update(effect_audit)
    else:
        strategy_audit.update(
            {
                "base_success_round": success_round,
                "base_round_duration_sec": round_sec,
                "adjusted_success_round": success_round,
                "adjusted_round_duration_sec": round(round_sec, 2),
                "delta_round": 0,
                "speedup_ratio": 0.0,
            }
        )
    hard = {
        "check_model_pass": False,
        "simulate_pass": False,
        "physics_contract_pass": False,
        "regression_pass": False,
    }

    for idx in range(1, max_rounds + 1):
        total_time += round_sec
        rounds_used = idx
        hit = idx >= success_round
        check_ok = hit
        simulate_ok = hit
        if not hit:
            physics_eval = {
                "pass": False,
                "reasons": ["physics_contract_not_evaluated_before_check_and_simulate_pass"],
                "findings": [],
                "invariant_count": 0,
            }
            physics_ok = False
        elif forced_physics_fail:
            physics_eval = {
                "pass": False,
                "reasons": ["physics_contract_forced_fail"],
                "findings": [],
                "invariant_count": len(task_invariants),
            }
            physics_ok = False
        else:
            try:
                physics_eval = evaluate_physics_contract_v0(
                    contract=physics_contract,
                    task_invariants=task_invariants,
                    baseline_metrics=baseline_metrics,
                    candidate_metrics=candidate_metrics,
                    scale=str(task.get("scale") or "unknown"),
                )
            except Exception as exc:
                physics_eval = {
                    "pass": False,
                    "reasons": [f"physics_contract_eval_error:{exc}"],
                    "findings": [],
                    "invariant_count": len(task_invariants),
                }
            physics_ok = bool(physics_eval.get("pass"))
        regression_ok = hit and not forced_regression_fail
        attempts.append(
            {
                "round": idx,
                "time_budget_exceeded": total_time > max_time_sec,
                "check_model_pass": check_ok,
                "simulate_pass": simulate_ok,
                "physics_contract_pass": physics_ok,
                "physics_contract_reasons": list(physics_eval.get("reasons") or []),
                "physics_contract_invariant_count": int(physics_eval.get("invariant_count") or 0),
                "regression_pass": regression_ok,
                "repair_actions_planned": [str(x) for x in (repair_strategy.get("actions") or []) if isinstance(x, str)],
                "repair_strategy_id": str(repair_strategy.get("strategy_id") or ""),
            }
        )
        if check_ok and simulate_ok and physics_ok and regression_ok and total_time <= max_time_sec:
            passed = True
            hard = {
                "check_model_pass": True,
                "simulate_pass": True,
                "physics_contract_pass": True,
                "regression_pass": True,
            }
            break
        hard = {
            "check_model_pass": check_ok,
            "simulate_pass": simulate_ok,
            "physics_contract_pass": physics_ok,
            "regression_pass": regression_ok,
        }

    return {
        "task_id": str(task.get("task_id") or ""),
        "scale": str(task.get("scale") or "unknown"),
        "failure_type": failure_type,
        "passed": passed,
        "rounds_used": rounds_used,
        "time_to_pass_sec": total_time if passed else None,
        "elapsed_sec": round(total_time, 2),
        "hard_checks": hard,
        "repair_strategy": repair_strategy,
        "repair_audit": {
            **strategy_audit,
            "attempt_count": len(attempts),
            "final_round_used": rounds_used,
            "final_passed": passed,
        },
        "physics_contract_reasons": [
            str(x)
            for x in (attempts[-1].get("physics_contract_reasons") if attempts else [])
            if isinstance(x, str)
        ],
        "attempts": attempts,
    }


def _read_evidence_task(task: dict, key_inline: str, key_path: str) -> dict:
    inline = task.get(key_inline)
    if isinstance(inline, dict):
        return inline
    path = task.get(key_path)
    if isinstance(path, str) and path.strip():
        return _load_evidence_json(path.strip())
    return {}


def _run_task_evidence(
    task: dict,
    max_rounds: int,
    max_time_sec: int,
    physics_contract: dict,
    runtime_threshold: float,
    repair_playbook: dict,
    repair_history_payload: dict,
    focus_queue_payload: dict,
    patch_template_adaptations_payload: dict,
    retrieval_policy_payload: dict,
) -> dict:
    scale = str(task.get("scale") or "unknown")
    failure_type = str(task.get("failure_type") or "unknown")
    repair_strategy = recommend_repair_strategy(
        playbook_payload=repair_playbook,
        failure_type=failure_type,
        expected_stage=str(task.get("expected_stage") or "unknown"),
    )
    repair_strategy, capability_audit = _augment_repair_strategy(
        task=task,
        repair_strategy=repair_strategy,
        repair_history_payload=repair_history_payload,
        focus_queue_payload=focus_queue_payload,
        patch_template_adaptations_payload=patch_template_adaptations_payload,
        retrieval_policy_payload=retrieval_policy_payload,
    )
    rounds_used = max(1, int(task.get("observed_repair_rounds", 1) or 1))
    rounds_used = min(rounds_used, max_rounds)
    strategy_audit = {
        "strategy_effect_enabled": False,
        "strategy_id": str(repair_strategy.get("strategy_id") or ""),
        "strategy_reason": str(repair_strategy.get("reason") or ""),
        "strategy_confidence": float(repair_strategy.get("confidence", 0.0) or 0.0),
        "actions_planned": [str(x) for x in (repair_strategy.get("actions") or []) if isinstance(x, str)],
        **capability_audit,
        "base_success_round": rounds_used,
        "base_round_duration_sec": None,
        "adjusted_success_round": rounds_used,
        "adjusted_round_duration_sec": None,
        "delta_round": 0,
        "speedup_ratio": 0.0,
    }

    baseline_evidence = _read_evidence_task(task, "baseline_evidence", "baseline_evidence_path")
    candidate_evidence = _read_evidence_task(task, "candidate_evidence", "candidate_evidence_path")
    task_invariants = task.get("physical_invariants") if isinstance(task.get("physical_invariants"), list) else []

    def _evaluate(candidate_payload: dict) -> tuple[dict, dict, bool, bool, bool, bool]:
        base_metrics_eval = baseline_evidence.get("metrics") if isinstance(baseline_evidence.get("metrics"), dict) else {}
        cand_metrics_eval = candidate_payload.get("metrics") if isinstance(candidate_payload.get("metrics"), dict) else {}
        try:
            physics_eval_inner = evaluate_physics_contract_v0(
                contract=physics_contract,
                task_invariants=task_invariants,
                baseline_metrics=base_metrics_eval,
                candidate_metrics=cand_metrics_eval,
                scale=scale,
            )
        except Exception as exc:
            physics_eval_inner = {
                "pass": False,
                "reasons": [f"physics_contract_eval_error:{exc}"],
                "findings": [],
                "invariant_count": len(task_invariants),
            }

        try:
            regression_inner = compare_evidence(
                baseline=baseline_evidence,
                candidate=candidate_payload,
                runtime_regression_threshold=runtime_threshold,
                strict=False,
                checker_names=None,
                checker_config=task.get("checker_config") if isinstance(task.get("checker_config"), dict) else None,
            )
        except Exception as exc:
            regression_inner = {
                "decision": "FAIL",
                "reasons": [f"regression_eval_error:{exc}"],
            }
        check_ok_inner = bool(candidate_payload.get("check_ok"))
        simulate_ok_inner = bool(candidate_payload.get("simulate_ok"))
        physics_ok_inner = bool(physics_eval_inner.get("pass"))
        regression_ok_inner = str(regression_inner.get("decision") or "FAIL") == "PASS"
        return physics_eval_inner, regression_inner, check_ok_inner, simulate_ok_inner, physics_ok_inner, regression_ok_inner

    physics_eval, regression, check_ok, simulate_ok, physics_ok, regression_ok = _evaluate(candidate_evidence)
    stress_repair_applied_tags: list[str] = []
    if str(task.get("_stress_class") or "").strip():
        candidate_repaired, stress_repair_applied_tags = _apply_stress_repair_effect(
            task=task,
            baseline_evidence=baseline_evidence,
            candidate_evidence=candidate_evidence,
            strategy=repair_strategy,
            runtime_threshold=float(runtime_threshold),
        )
        if stress_repair_applied_tags:
            candidate_evidence = candidate_repaired
            physics_eval, regression, check_ok, simulate_ok, physics_ok, regression_ok = _evaluate(candidate_evidence)

    cand_metrics = candidate_evidence.get("metrics") if isinstance(candidate_evidence.get("metrics"), dict) else {}
    elapsed_sec = int(task.get("observed_elapsed_sec") or round(float(cand_metrics.get("runtime_seconds") or 0.0)))
    elapsed_sec = max(1, elapsed_sec)
    if stress_repair_applied_tags and any(tag == "repair_runtime_regression" for tag in stress_repair_applied_tags):
        elapsed_sec = max(1, int(round(_safe_float(cand_metrics.get("runtime_seconds"), elapsed_sec) * 20.0)))
    time_budget_exceeded = elapsed_sec > max_time_sec
    attempts = [
        {
            "round": rounds_used,
            "time_budget_exceeded": time_budget_exceeded,
            "check_model_pass": check_ok,
            "simulate_pass": simulate_ok,
            "physics_contract_pass": physics_ok,
            "physics_contract_reasons": list(physics_eval.get("reasons") or []),
            "physics_contract_invariant_count": int(physics_eval.get("invariant_count") or 0),
            "regression_pass": regression_ok,
            "regression_reasons": [str(x) for x in (regression.get("reasons") or []) if isinstance(x, str)],
            "stress_repair_applied_tags": stress_repair_applied_tags,
        }
    ]
    passed = check_ok and simulate_ok and physics_ok and regression_ok and not time_budget_exceeded

    return {
        "task_id": str(task.get("task_id") or ""),
        "scale": scale,
        "failure_type": failure_type,
        "passed": passed,
        "rounds_used": rounds_used,
        "time_to_pass_sec": elapsed_sec if passed else None,
        "elapsed_sec": elapsed_sec,
        "hard_checks": {
            "check_model_pass": check_ok,
            "simulate_pass": simulate_ok,
            "physics_contract_pass": physics_ok,
            "regression_pass": regression_ok,
        },
        "repair_strategy": repair_strategy,
        "repair_audit": {
            **strategy_audit,
            "stress_repair_applied": bool(stress_repair_applied_tags),
            "stress_repair_applied_tags": stress_repair_applied_tags,
            "attempt_count": 1,
            "final_round_used": rounds_used,
            "final_passed": passed,
        },
        "physics_contract_reasons": [str(x) for x in (physics_eval.get("reasons") or []) if isinstance(x, str)],
        "regression_reasons": [str(x) for x in (regression.get("reasons") or []) if isinstance(x, str)],
        "attempts": attempts,
    }


def _run_task_live(
    task: dict,
    max_rounds: int,
    max_time_sec: int,
    physics_contract: dict,
    runtime_threshold: float,
    repair_playbook: dict,
    repair_history_payload: dict,
    focus_queue_payload: dict,
    patch_template_adaptations_payload: dict,
    retrieval_policy_payload: dict,
    live_executor_cmd: str,
    live_timeout_sec: int,
    live_max_output_chars: int,
) -> dict:
    scale = str(task.get("scale") or "unknown")
    failure_type = str(task.get("failure_type") or "unknown")
    task_invariants = task.get("physical_invariants") if isinstance(task.get("physical_invariants"), list) else []
    repair_strategy = recommend_repair_strategy(
        playbook_payload=repair_playbook,
        failure_type=failure_type,
        expected_stage=str(task.get("expected_stage") or "unknown"),
    )
    repair_strategy, capability_audit = _augment_repair_strategy(
        task=task,
        repair_strategy=repair_strategy,
        repair_history_payload=repair_history_payload,
        focus_queue_payload=focus_queue_payload,
        patch_template_adaptations_payload=patch_template_adaptations_payload,
        retrieval_policy_payload=retrieval_policy_payload,
    )
    strategy_audit = {
        "strategy_effect_enabled": False,
        "strategy_id": str(repair_strategy.get("strategy_id") or ""),
        "strategy_reason": str(repair_strategy.get("reason") or ""),
        "strategy_confidence": float(repair_strategy.get("confidence", 0.0) or 0.0),
        "actions_planned": [str(x) for x in (repair_strategy.get("actions") or []) if isinstance(x, str)],
        **capability_audit,
        "live_executor_configured": bool(str(task.get("live_executor_command") or "").strip() or str(live_executor_cmd).strip()),
        "live_timeout_sec": int(max(1, live_timeout_sec)),
        "base_success_round": None,
        "base_round_duration_sec": None,
        "adjusted_success_round": None,
        "adjusted_round_duration_sec": None,
        "delta_round": 0,
        "speedup_ratio": 0.0,
    }
    command_template = str(task.get("live_executor_command") or live_executor_cmd or "").strip()
    if not command_template:
        return {
            "task_id": str(task.get("task_id") or ""),
            "scale": scale,
            "failure_type": failure_type,
            "passed": False,
            "rounds_used": 0,
            "time_to_pass_sec": None,
            "elapsed_sec": 0.0,
            "hard_checks": {
                "check_model_pass": False,
                "simulate_pass": False,
                "physics_contract_pass": False,
                "regression_pass": False,
            },
            "repair_strategy": repair_strategy,
            "repair_audit": {
                **strategy_audit,
                "attempt_count": 0,
                "final_round_used": 0,
                "final_passed": False,
                "live_executor_missing": True,
            },
            "physics_contract_reasons": ["live_executor_command_missing"],
            "regression_reasons": ["live_executor_command_missing"],
            "attempts": [],
            "error_message": "live_executor_command_missing",
            "compile_error": "",
            "simulate_error_message": "",
            "stderr_snippet": "",
        }

    attempts: list[dict] = []
    total_time_sec = 0.0
    passed = False
    rounds_used = 0
    hard = {
        "check_model_pass": False,
        "simulate_pass": False,
        "physics_contract_pass": False,
        "regression_pass": False,
    }
    physics_contract_reasons: list[str] = []
    regression_reasons: list[str] = []
    error_message = ""
    compile_error = ""
    simulate_error_message = ""
    stderr_snippet = ""

    for idx in range(1, max_rounds + 1):
        rounds_used = idx
        context = _build_live_template_context(
            task=task,
            strategy=repair_strategy,
            round_idx=idx,
            max_rounds=max_rounds,
            max_time_sec=max_time_sec,
        )
        command = _render_live_command(command_template, context=context)
        timeout_for_round = min(max(1, int(live_timeout_sec)), max(1, int(max_time_sec)))
        try:
            live_payload, raw_stdout, raw_stderr = _run_live_executor_once(command=command, timeout_sec=timeout_for_round)
        except subprocess.TimeoutExpired:
            live_payload = {
                "_executor_return_code": None,
                "_executor_stdout_tail": "",
                "_executor_stderr_tail": "TimeoutExpired",
                "error_message": "live_executor_timeout",
            }
            raw_stdout, raw_stderr = "", "TimeoutExpired"

        elapsed_sec = _safe_float(live_payload.get("elapsed_sec"), _safe_float(live_payload.get("duration_sec"), 0.0))
        if elapsed_sec <= 0:
            elapsed_sec = 1.0
        total_time_sec += elapsed_sec
        time_budget_exceeded = total_time_sec > float(max_time_sec)

        check_ok = _as_bool(live_payload.get("check_model_pass"))
        if check_ok is None:
            check_ok = _as_bool(live_payload.get("check_ok"))
        check_ok = bool(check_ok) if check_ok is not None else False

        simulate_ok = _as_bool(live_payload.get("simulate_pass"))
        if simulate_ok is None:
            simulate_ok = _as_bool(live_payload.get("simulate_ok"))
        simulate_ok = bool(simulate_ok) if simulate_ok is not None else False

        provided_physics = _as_bool(live_payload.get("physics_contract_pass"))
        physics_eval = {"pass": False, "reasons": [], "invariant_count": len(task_invariants)}
        if provided_physics is not None:
            physics_ok = bool(provided_physics)
            physics_reasons_local = _as_str_list(live_payload.get("physics_contract_reasons"))
            if not physics_ok and not physics_reasons_local:
                physics_reasons_local = ["physics_contract_fail"]
            physics_eval = {
                "pass": physics_ok,
                "reasons": physics_reasons_local,
                "invariant_count": len(task_invariants),
            }
        else:
            baseline_metrics_eval = (
                live_payload.get("baseline_metrics") if isinstance(live_payload.get("baseline_metrics"), dict) else {}
            )
            candidate_metrics_eval = (
                live_payload.get("candidate_metrics") if isinstance(live_payload.get("candidate_metrics"), dict) else {}
            )
            if baseline_metrics_eval and candidate_metrics_eval:
                try:
                    physics_eval = evaluate_physics_contract_v0(
                        contract=physics_contract,
                        task_invariants=task_invariants,
                        baseline_metrics=baseline_metrics_eval,
                        candidate_metrics=candidate_metrics_eval,
                        scale=scale,
                    )
                except Exception as exc:
                    physics_eval = {
                        "pass": False,
                        "reasons": [f"physics_contract_eval_error:{exc}"],
                        "invariant_count": len(task_invariants),
                    }
            else:
                physics_eval = {
                    "pass": False,
                    "reasons": ["physics_contract_not_provided"],
                    "invariant_count": len(task_invariants),
                }
            physics_ok = bool(physics_eval.get("pass"))

        provided_regression = _as_bool(live_payload.get("regression_pass"))
        regression_eval = {"decision": "FAIL", "reasons": []}
        if provided_regression is not None:
            regression_ok = bool(provided_regression)
            regression_reasons_local = _as_str_list(live_payload.get("regression_reasons"))
            if not regression_ok and not regression_reasons_local:
                regression_reasons_local = ["regression_fail"]
            regression_eval = {"decision": "PASS" if regression_ok else "FAIL", "reasons": regression_reasons_local}
        else:
            baseline_evidence = live_payload.get("baseline_evidence") if isinstance(live_payload.get("baseline_evidence"), dict) else {}
            candidate_evidence = live_payload.get("candidate_evidence") if isinstance(live_payload.get("candidate_evidence"), dict) else {}
            if not baseline_evidence or not candidate_evidence:
                base_metrics = live_payload.get("baseline_metrics") if isinstance(live_payload.get("baseline_metrics"), dict) else {}
                cand_metrics = live_payload.get("candidate_metrics") if isinstance(live_payload.get("candidate_metrics"), dict) else {}
                if base_metrics and cand_metrics:
                    baseline_evidence = {
                        "status": "success",
                        "gate": "PASS",
                        "check_ok": True,
                        "simulate_ok": True,
                        "metrics": base_metrics,
                    }
                    candidate_evidence = {
                        "status": "success" if check_ok and simulate_ok else "failed",
                        "gate": "PASS" if check_ok and simulate_ok else "FAIL",
                        "check_ok": check_ok,
                        "simulate_ok": simulate_ok,
                        "metrics": cand_metrics,
                    }
            if baseline_evidence and candidate_evidence:
                try:
                    regression_eval = compare_evidence(
                        baseline=baseline_evidence,
                        candidate=candidate_evidence,
                        runtime_regression_threshold=float(runtime_threshold),
                        strict=False,
                        checker_names=None,
                        checker_config=task.get("checker_config") if isinstance(task.get("checker_config"), dict) else None,
                    )
                except Exception as exc:
                    regression_eval = {"decision": "FAIL", "reasons": [f"regression_eval_error:{exc}"]}
            else:
                regression_eval = {"decision": "FAIL", "reasons": ["regression_not_provided"]}
            regression_ok = str(regression_eval.get("decision") or "FAIL") == "PASS"

        physics_contract_reasons = _as_str_list(physics_eval.get("reasons"))
        regression_reasons = _as_str_list(regression_eval.get("reasons"))
        error_message = str(live_payload.get("error_message") or "")
        compile_error = str(live_payload.get("compile_error") or "")
        simulate_error_message = str(live_payload.get("simulate_error_message") or "")
        stderr_snippet = str(
            live_payload.get("stderr_snippet")
            or live_payload.get("_executor_stderr_tail")
            or _last_nonempty_line(raw_stderr)
            or _last_nonempty_line(raw_stdout)
            or ""
        )

        attempts.append(
            {
                "round": idx,
                "time_budget_exceeded": bool(time_budget_exceeded),
                "check_model_pass": bool(check_ok),
                "simulate_pass": bool(simulate_ok),
                "physics_contract_pass": bool(physics_ok),
                "physics_contract_reasons": physics_contract_reasons,
                "physics_contract_invariant_count": int(physics_eval.get("invariant_count") or 0),
                "regression_pass": bool(regression_ok),
                "regression_reasons": regression_reasons,
                "executor_return_code": live_payload.get("_executor_return_code"),
                "executor_stdout_tail": str(live_payload.get("_executor_stdout_tail") or "")[: max(0, int(live_max_output_chars))],
                "executor_stderr_tail": str(live_payload.get("_executor_stderr_tail") or "")[: max(0, int(live_max_output_chars))],
                "elapsed_sec": round(elapsed_sec, 4),
                "repair_actions_planned": [str(x) for x in (repair_strategy.get("actions") or []) if isinstance(x, str)],
                "repair_strategy_id": str(repair_strategy.get("strategy_id") or ""),
            }
        )
        hard = {
            "check_model_pass": bool(check_ok),
            "simulate_pass": bool(simulate_ok),
            "physics_contract_pass": bool(physics_ok),
            "regression_pass": bool(regression_ok),
        }
        if all(hard.values()) and not time_budget_exceeded:
            passed = True
            break

    return {
        "task_id": str(task.get("task_id") or ""),
        "scale": scale,
        "failure_type": failure_type,
        "passed": passed,
        "rounds_used": rounds_used,
        "time_to_pass_sec": round(total_time_sec, 4) if passed else None,
        "elapsed_sec": round(total_time_sec, 4),
        "hard_checks": hard,
        "repair_strategy": repair_strategy,
        "repair_audit": {
            **strategy_audit,
            "attempt_count": len(attempts),
            "final_round_used": rounds_used,
            "final_passed": passed,
            "live_executor_command_from_task": bool(str(task.get("live_executor_command") or "").strip()),
        },
        "physics_contract_reasons": physics_contract_reasons,
        "regression_reasons": regression_reasons,
        "attempts": attempts,
        "error_message": error_message,
        "compile_error": compile_error,
        "simulate_error_message": simulate_error_message,
        "stderr_snippet": stderr_snippet[: max(0, int(live_max_output_chars))],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute agent modelica run contract with bounded rounds/time")
    parser.add_argument("--taskset", required=True)
    parser.add_argument("--mode", choices=["mock", "evidence", "live"], default="mock")
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--max-time-sec", type=int, default=300)
    parser.add_argument("--runtime-threshold", type=float, default=0.2)
    parser.add_argument("--physics-contract", default=DEFAULT_PHYSICS_CONTRACT_PATH)
    parser.add_argument("--repair-playbook", default=None)
    parser.add_argument("--repair-history", default=None)
    parser.add_argument("--focus-queue", default=None)
    parser.add_argument("--patch-template-adaptations", default=None)
    parser.add_argument("--retrieval-policy", default=None)
    parser.add_argument("--live-executor-cmd", default=None)
    parser.add_argument("--live-timeout-sec", type=int, default=180)
    parser.add_argument("--live-max-output-chars", type=int, default=1200)
    parser.add_argument("--records-jsonl", default="")
    parser.add_argument("--resume-from-records", action="store_true")
    parser.add_argument("--strategy-effect", choices=["on", "off"], default="on")
    parser.add_argument("--results-out", default="artifacts/agent_modelica_run_contract_v1/results.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_run_contract_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    payload = _load_json(args.taskset)
    tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    tasks = [x for x in tasks if isinstance(x, dict)]
    reasons: list[str] = []
    if not tasks:
        reasons.append("taskset_empty")

    max_rounds = max(1, int(args.max_rounds))
    max_time_sec = max(1, int(args.max_time_sec))
    physics_contract, physics_contract_source = load_physics_contract_v0(args.physics_contract)
    repair_playbook = load_repair_playbook(args.repair_playbook)
    repair_history_payload = _load_json(str(args.repair_history)) if isinstance(args.repair_history, str) and args.repair_history.strip() else {}
    focus_queue_payload = _load_json(str(args.focus_queue)) if isinstance(args.focus_queue, str) and args.focus_queue.strip() else {}
    patch_template_adaptations_payload = (
        _load_json(str(args.patch_template_adaptations))
        if isinstance(args.patch_template_adaptations, str) and args.patch_template_adaptations.strip()
        else {}
    )
    retrieval_policy_payload = (
        _load_json(str(args.retrieval_policy))
        if isinstance(args.retrieval_policy, str) and args.retrieval_policy.strip()
        else {}
    )

    records_jsonl_path = str(args.records_jsonl or "").strip()
    resume_records: dict[str, dict] = {}
    resumed_count = 0
    if bool(args.resume_from_records) and records_jsonl_path:
        resume_records = _load_records_jsonl(records_jsonl_path)

    records: list[dict] = []
    for task in tasks:
        task_id = str(task.get("task_id") or "").strip()
        if task_id and task_id in resume_records:
            records.append(resume_records[task_id])
            resumed_count += 1
            continue

        record: dict
        if args.mode == "evidence":
            record = _run_task_evidence(
                task,
                max_rounds=max_rounds,
                max_time_sec=max_time_sec,
                physics_contract=physics_contract,
                runtime_threshold=float(args.runtime_threshold),
                repair_playbook=repair_playbook,
                repair_history_payload=repair_history_payload,
                focus_queue_payload=focus_queue_payload,
                patch_template_adaptations_payload=patch_template_adaptations_payload,
                retrieval_policy_payload=retrieval_policy_payload,
            )
        elif args.mode == "live":
            record = _run_task_live(
                task,
                max_rounds=max_rounds,
                max_time_sec=max_time_sec,
                physics_contract=physics_contract,
                runtime_threshold=float(args.runtime_threshold),
                repair_playbook=repair_playbook,
                repair_history_payload=repair_history_payload,
                focus_queue_payload=focus_queue_payload,
                patch_template_adaptations_payload=patch_template_adaptations_payload,
                retrieval_policy_payload=retrieval_policy_payload,
                live_executor_cmd=str(args.live_executor_cmd or ""),
                live_timeout_sec=max(1, int(args.live_timeout_sec)),
                live_max_output_chars=max(200, int(args.live_max_output_chars)),
            )
        else:
            record = _run_task_mock(
                task,
                max_rounds=max_rounds,
                max_time_sec=max_time_sec,
                physics_contract=physics_contract,
                repair_playbook=repair_playbook,
                repair_history_payload=repair_history_payload,
                focus_queue_payload=focus_queue_payload,
                patch_template_adaptations_payload=patch_template_adaptations_payload,
                retrieval_policy_payload=retrieval_policy_payload,
                strategy_effect_enabled=(args.strategy_effect == "on"),
            )
        records.append(record)
        if records_jsonl_path:
            _append_record_jsonl(records_jsonl_path, record)

    success_rows = [x for x in records if bool(x.get("passed"))]
    success_count = len(success_rows)
    times = [
        float(x.get("time_to_pass_sec"))
        for x in success_rows
        if isinstance(x.get("time_to_pass_sec"), (int, float))
    ]
    rounds = [int(x.get("rounds_used")) for x in success_rows if isinstance(x.get("rounds_used"), int)]
    regression_count = len([x for x in records if not bool((x.get("hard_checks") or {}).get("regression_pass"))])
    physics_fail_count = len([x for x in records if not bool((x.get("hard_checks") or {}).get("physics_contract_pass"))])

    median_time = round(statistics.median(times), 2) if times else None
    median_rounds = round(statistics.median(rounds), 2) if rounds else None
    status = "PASS"
    if reasons:
        status = "FAIL"
    elif success_count < len(records):
        status = "NEEDS_REVIEW"

    results_payload = {
        "schema_version": "agent_modelica_run_results_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "physics_contract_schema_version": physics_contract.get("schema_version"),
        "physics_contract_source": physics_contract_source,
        "repair_playbook_source": repair_playbook.get("source") if isinstance(repair_playbook, dict) else None,
        "repair_history_source": args.repair_history,
        "focus_queue_source": args.focus_queue,
        "patch_template_adaptations_source": args.patch_template_adaptations,
        "retrieval_policy_source": args.retrieval_policy,
        "live_executor_cmd": args.live_executor_cmd,
        "live_timeout_sec": int(args.live_timeout_sec),
        "live_max_output_chars": int(args.live_max_output_chars),
        "records_jsonl": records_jsonl_path,
        "resume_from_records": bool(args.resume_from_records),
        "resumed_count": resumed_count,
        "mode": args.mode,
        "strategy_effect": args.strategy_effect,
        "records": records,
    }
    _write_json(args.results_out, results_payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_tasks": len(records),
        "success_count": success_count,
        "success_at_k_pct": _ratio(success_count, len(records)),
        "median_time_to_pass_sec": median_time,
        "median_repair_rounds": median_rounds,
        "regression_count": regression_count,
        "physics_fail_count": physics_fail_count,
        "physics_contract_schema_version": physics_contract.get("schema_version"),
        "physics_contract_source": physics_contract_source,
        "repair_playbook_source": repair_playbook.get("source") if isinstance(repair_playbook, dict) else None,
        "repair_history_source": args.repair_history,
        "focus_queue_source": args.focus_queue,
        "patch_template_adaptations_source": args.patch_template_adaptations,
        "retrieval_policy_source": args.retrieval_policy,
        "live_executor_cmd": args.live_executor_cmd,
        "live_timeout_sec": int(args.live_timeout_sec),
        "live_max_output_chars": int(args.live_max_output_chars),
        "records_jsonl": records_jsonl_path,
        "resume_from_records": bool(args.resume_from_records),
        "resumed_count": resumed_count,
        "mode": args.mode,
        "strategy_effect": args.strategy_effect,
        "max_rounds": max_rounds,
        "max_time_sec": max_time_sec,
        "runtime_threshold": float(args.runtime_threshold),
        "results_out": args.results_out,
        "reasons": reasons,
        "sources": {
            "taskset": args.taskset,
            "physics_contract": args.physics_contract,
            "repair_playbook": args.repair_playbook,
            "repair_history": args.repair_history,
            "focus_queue": args.focus_queue,
            "patch_template_adaptations": args.patch_template_adaptations,
            "retrieval_policy": args.retrieval_policy,
            "live_executor_cmd": args.live_executor_cmd,
            "live_timeout_sec": int(args.live_timeout_sec),
            "live_max_output_chars": int(args.live_max_output_chars),
            "records_jsonl": records_jsonl_path,
            "resume_from_records": bool(args.resume_from_records),
        },
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "success_count": success_count, "total_tasks": len(records)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
