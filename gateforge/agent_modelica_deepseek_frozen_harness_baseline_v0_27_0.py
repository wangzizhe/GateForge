from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from .agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text
from .agent_modelica_observation_contract_v0_26_1 import build_observation_event, validate_observation_event
from .agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "deepseek_frozen_harness_baseline_v0_27_0"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

BUILTIN_CASES = [
    {
        "case_id": "v0270_missing_equation_minimal",
        "model_name": "MissingEquationMinimal",
        "failure_type": "model_check_error",
        "workflow_goal": "Repair the Modelica model so checkModel succeeds while preserving the model name.",
        "model_text": """model MissingEquationMinimal
  Real x;
end MissingEquationMinimal;
""",
    },
    {
        "case_id": "v0270_duplicate_equation_minimal",
        "model_name": "DuplicateEquationMinimal",
        "failure_type": "model_check_error",
        "workflow_goal": "Repair the Modelica model so checkModel succeeds while preserving the model name.",
        "model_text": """model DuplicateEquationMinimal
  Real x;
equation
  x = 1;
  x = 2;
end DuplicateEquationMinimal;
""",
    },
]

CheckFn = Callable[[str, str], tuple[bool, str]]
RepairFn = Callable[..., tuple[str | None, str, str]]


def _strip_ws(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def run_omc_check(model_text: str, model_name: str) -> tuple[bool, str]:
    with temporary_workspace("gf_v0270_live_") as ws:
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
        _, output, check_ok, _simulate_ok = run_check_and_simulate(
            workspace=workspace,
            model_load_files=list(layout.model_load_files),
            model_name=layout.model_identifier,
            timeout_sec=180,
            backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
            stop_time=0.05,
            intervals=5,
            extra_model_loads=[],
        )
        return bool(check_ok), str(output or "")


def _call_repair(
    *,
    repair_fn: RepairFn,
    planner_backend: str,
    model_text: str,
    model_name: str,
    failure_type: str,
    workflow_goal: str,
    error_excerpt: str,
    current_round: int,
    repair_history: list[dict[str, Any]],
) -> tuple[str | None, str, str]:
    return repair_fn(
        planner_backend=planner_backend,
        original_text=model_text,
        failure_type=failure_type,
        expected_stage="check",
        error_excerpt=error_excerpt[:12000],
        repair_actions=[],
        model_name=model_name,
        workflow_goal=workflow_goal,
        current_round=current_round,
        repair_history=repair_history,
    )


def run_live_case(
    case: dict[str, Any],
    *,
    max_rounds: int,
    planner_backend: str = "auto",
    check_fn: CheckFn = run_omc_check,
    repair_fn: RepairFn = llm_repair_model_text,
) -> dict[str, Any]:
    current_text = str(case["model_text"])
    model_name = str(case["model_name"])
    case_id = str(case["case_id"])
    workflow_goal = str(case.get("workflow_goal") or "")
    failure_type = str(case.get("failure_type") or "model_check_error")
    repair_history: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    provider_name = ""
    final_verdict = "FAILED"

    for round_index in range(1, max(1, int(max_rounds)) + 1):
        check_ok_before, raw_omc_before = check_fn(current_text, model_name)
        observation = build_observation_event(
            run_id="v0.27.0_deepseek_frozen_harness_baseline",
            case_id=case_id,
            repair_round_index=round_index,
            model_text=current_text,
            workflow_goal=workflow_goal,
            raw_omc_feedback=raw_omc_before,
            provider_name=provider_name or "pending",
            model_profile="deepseek-v4-flash",
        )
        observation_errors = validate_observation_event(observation)
        observations.append({"event": observation, "validation_errors": observation_errors})
        if check_ok_before:
            final_verdict = "PASS"
            attempts.append(
                {
                    "round": round_index,
                    "check_pass_before_patch": True,
                    "llm_called": False,
                    "provider": provider_name,
                    "llm_error": "",
                }
            )
            break

        patched_text, llm_error, provider = _call_repair(
            repair_fn=repair_fn,
            planner_backend=planner_backend,
            model_text=current_text,
            model_name=model_name,
            failure_type=failure_type,
            workflow_goal=workflow_goal,
            error_excerpt=raw_omc_before,
            current_round=round_index,
            repair_history=repair_history,
        )
        provider_name = provider
        attempt: dict[str, Any] = {
            "round": round_index,
            "check_pass_before_patch": False,
            "llm_called": True,
            "provider": provider,
            "llm_error": llm_error,
            "patched_text_present": isinstance(patched_text, str) and bool(str(patched_text).strip()),
            "model_changed": False,
            "check_pass_after_patch": None,
            "raw_omc_after_patch": "",
        }
        if not isinstance(patched_text, str) or not patched_text.strip():
            attempts.append(attempt)
            break
        attempt["model_changed"] = _strip_ws(patched_text) != _strip_ws(current_text)
        check_ok_after, raw_omc_after = check_fn(patched_text, model_name)
        attempt["check_pass_after_patch"] = check_ok_after
        attempt["raw_omc_after_patch"] = raw_omc_after
        attempts.append(attempt)
        repair_history.append(
            {
                "round": round_index,
                "provider": provider,
                "patched_text_present": True,
                "model_changed": attempt["model_changed"],
                "check_pass_after_patch": check_ok_after,
                "omc_summary": raw_omc_after[:1200],
            }
        )
        current_text = patched_text
        if check_ok_after:
            final_verdict = "PASS"
            break

    repair_round_count = sum(1 for attempt in attempts if attempt.get("llm_called") and attempt.get("patched_text_present"))
    result = {
        "case_id": case_id,
        "model_name": model_name,
        "provider": provider_name,
        "model_profile": "deepseek-v4-flash",
        "run_mode": "raw_only",
        "final_verdict": final_verdict,
        "repair_round_count": repair_round_count,
        "executor_attempt_count": len(attempts),
        "true_multi_turn": final_verdict == "PASS" and repair_round_count >= 2,
        "attempts": attempts,
        "observation_validation_error_count": sum(len(row["validation_errors"]) for row in observations),
        "observations": observations,
        "final_model_text": current_text,
    }
    return result


def run_deepseek_frozen_harness_baseline(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    cases: list[dict[str, Any]] | None = None,
    limit: int = 1,
    max_rounds: int = 2,
    planner_backend: str = "auto",
    check_fn: CheckFn = run_omc_check,
    repair_fn: RepairFn = llm_repair_model_text,
) -> dict[str, Any]:
    selected = list(cases or BUILTIN_CASES)[: max(0, int(limit))]
    results = [
        run_live_case(
            case,
            max_rounds=max_rounds,
            planner_backend=planner_backend,
            check_fn=check_fn,
            repair_fn=repair_fn,
        )
        for case in selected
    ]
    total = len(results)
    pass_count = sum(1 for row in results if row.get("final_verdict") == "PASS")
    provider_errors = sum(1 for row in results if any(str(a.get("llm_error") or "") for a in row.get("attempts", [])))
    observation_error_count = sum(int(row.get("observation_validation_error_count") or 0) for row in results)
    summary = {
        "version": "v0.27.0",
        "status": "PASS" if total and observation_error_count == 0 else "REVIEW",
        "analysis_scope": "deepseek_frozen_harness_small_live_baseline",
        "run_mode": "raw_only",
        "provider": "deepseek",
        "model_profile": "deepseek-v4-flash",
        "case_count": total,
        "pass_count": pass_count,
        "provider_error_count": provider_errors,
        "true_multi_turn_count": sum(1 for row in results if row.get("true_multi_turn")),
        "observation_validation_error_count": observation_error_count,
        "sample_interpretation": "small_live_baseline_not_representative_benchmark",
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "comparative_claim_made": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": (
            "deepseek_small_live_baseline_artifact_ready"
            if total and observation_error_count == 0
            else "deepseek_small_live_baseline_needs_review"
        ),
        "next_focus": "expand_deepseek_live_baseline_only_after_review",
    }
    write_outputs(out_dir=out_dir, summary=summary, results=results)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], results: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for row in results:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    patched_dir = out_dir / "patched_models"
    patched_dir.mkdir(exist_ok=True)
    for row in results:
        (patched_dir / f"{row['case_id']}.mo").write_text(str(row.get("final_model_text") or ""), encoding="utf-8")
