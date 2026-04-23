"""Representation routing experiment for v0.19.56.

The router only chooses which representation block is shown to the LLM. It does
not generate repair hints, rank candidates, or patch the model.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN", "240")
os.environ.setdefault("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", "180")

from gateforge.agent_modelica_candidate_ranker_v1 import rank_candidates  # noqa: E402
from gateforge.agent_modelica_l2_plan_replan_engine_v1 import (  # noqa: E402
    llm_repair_model_text_multi,
)
from scripts.analyze_representation_effect_stratification_v0_19_56 import (  # noqa: E402
    build_analysis as build_existing_stratification,
)
from gateforge.experiment_runner_shared import (  # noqa: E402
    ALL_HARD_CASES,
    DOCKER_IMAGE,
    load_broken_model,
    load_case_info,
    run_check_and_simulate_omc,
    run_check_only_omc,
)
from scripts.run_representation_trajectory_v0_19_56 import (  # noqa: E402
    MAX_ROUNDS,
    _build_representation_context,
    compute_summary,
)

NUM_CANDIDATES = 5
ROUTED_MODE = "signal-routed-c5"
EXISTING_TRAJECTORY_DIR = REPO_ROOT / "artifacts" / "representation_trajectory_v0_19_56"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "representation_routing_trajectory_v0_19_56"
NO_REMAINING_EQUATION_RE = re.compile(
    r"Warning:\s+Variable\s+[A-Za-z_][A-Za-z0-9_]*\s+does not have any remaining equation"
)


def count_underdetermined_warnings(omc_output: str) -> int:
    return len(NO_REMAINING_EQUATION_RE.findall(omc_output or ""))


def select_signal_route(*, omc_output: str) -> str:
    """Select a representation from generic OMC signal shape only.

    The deployable router must not inspect case ids, model-family names, or
    specific variable names. It only uses the count of underdetermined-variable
    warnings as a coarse representation-selection signal.
    """
    warning_count = count_underdetermined_warnings(omc_output)
    if warning_count >= 2:
        return "blt-c5"
    if warning_count == 1:
        return "causal-c5"
    return "baseline-c5"


def build_oracle_existing_summary(
    trajectory_dir: Path = EXISTING_TRAJECTORY_DIR,
) -> dict[str, Any]:
    """Compute the diagnostic upper bound from already-run representation arms."""
    stratification = build_existing_stratification(trajectory_dir)
    return {
        "mode": "oracle-existing",
        "source_artifact": str(trajectory_dir),
        "case_count": stratification["case_count"],
        "pass_count": stratification["union_pass_count"],
        "pass_rate": stratification["union_pass_rate"],
        "route_counts": stratification["route_counts"],
        "note": (
            "Diagnostic upper bound only. It chooses from already-run arms after "
            "observing their outcomes and is not a deployable router."
        ),
    }


def select_feedback_output(
    *,
    check_ok: bool,
    check_output: str,
    simulate_ok: bool | None,
    simulate_output: str,
) -> tuple[str, str]:
    """Select the real tool feedback to show next.

    This is wiring only: it chooses which stage output is relevant. It does not
    diagnose the failure or propose any repair.
    """
    if not check_ok:
        if count_underdetermined_warnings(simulate_output) > count_underdetermined_warnings(check_output):
            return "check_and_simulate", simulate_output
        if simulate_output and len(simulate_output) > len(check_output):
            return "check_and_simulate", simulate_output
        return "check", check_output
    if simulate_ok is False:
        return "simulate", simulate_output
    return "none", ""


def _run_single_case(
    *,
    candidate_id: str,
    out_dir: Path,
    planner_backend: str,
    skip_existing: bool = False,
) -> dict[str, Any]:
    out_path = out_dir / f"{candidate_id}_{ROUTED_MODE}.json"
    if skip_existing and out_path.exists():
        return json.loads(out_path.read_text(encoding="utf-8"))

    print(f"  [{ROUTED_MODE}/N={NUM_CANDIDATES}] {candidate_id}")
    case_info = load_case_info(candidate_id)
    current_text = load_broken_model(candidate_id)
    model_name = case_info.get("model_name", candidate_id.split("_")[1] + "_v0")
    workflow_goal = case_info.get("workflow_goal", "")

    rounds: list[dict[str, Any]] = []
    final_pass = False
    final_round = 0

    for round_num in range(1, MAX_ROUNDS + 1):
        cur_check_ok, cur_omc_output = run_check_only_omc(current_text, model_name, workspace_prefix="gf_v01956_chk_")
        feedback_stage = "check"
        feedback_output = cur_omc_output
        chk, sim, sim_output = _run_check_and_simulate(current_text, model_name)
        if chk and sim:
            final_pass = True
            final_round = round_num - 1 if round_num > 1 else 0
            print(f"    -> PASS (already passes check at round {round_num})")
            break
        feedback_stage, feedback_output = select_feedback_output(
            check_ok=cur_check_ok,
            check_output=cur_omc_output,
            simulate_ok=sim,
            simulate_output=sim_output,
        )

        selected_representation_mode = select_signal_route(
            omc_output=feedback_output,
        )
        context_text, context_label, context_obj = _build_representation_context(
            mode=selected_representation_mode,
            model_text=current_text,
            omc_output=feedback_output,
        )

        candidates = llm_repair_model_text_multi(
            planner_backend=planner_backend,
            original_text=current_text,
            failure_type="underconstrained_system",
            expected_stage="check",
            error_excerpt=feedback_output[:12000],
            repair_actions=[],
            model_name=model_name,
            workflow_goal=workflow_goal,
            current_round=round_num,
            num_candidates=NUM_CANDIDATES,
            context_block=context_text,
            context_block_label=context_label,
        )

        def _runner(text: str) -> tuple[bool, str]:
            return run_check_only_omc(text, model_name, workspace_prefix="gf_v01956_chk_")

        ranked = rank_candidates(candidates, run_omc=_runner)
        coverage_check = sum(1 for item in ranked if item.check_pass)
        top = ranked[0] if ranked else None

        simulate_attempts: list[dict[str, Any]] = []
        for item in ranked:
            if not item.check_pass:
                break
            if not item.patched_text:
                continue
            chk, sim, _ = run_check_and_simulate_omc(item.patched_text, model_name, workspace_prefix="gf_v01956_sim_")
            simulate_attempts.append(
                {
                    "candidate_id": item.candidate_id,
                    "temperature_used": item.temperature_used,
                    "check_pass_again": bool(chk),
                    "simulate_pass": bool(sim),
                }
            )
        coverage_simulate = sum(1 for item in simulate_attempts if item["simulate_pass"])

        chosen_id = None
        chosen_temp = None
        chosen_text = None
        chosen_check_pass = False
        chosen_simulate_pass = False
        for attempt in simulate_attempts:
            if attempt["simulate_pass"]:
                chosen_id = attempt["candidate_id"]
                chosen_temp = attempt["temperature_used"]
                chosen_check_pass = True
                chosen_simulate_pass = True
                for ranked_item in ranked:
                    if ranked_item.candidate_id == chosen_id:
                        chosen_text = ranked_item.patched_text
                        break
                break
        if chosen_id is None:
            for ranked_item in ranked:
                if ranked_item.patched_text:
                    chosen_id = ranked_item.candidate_id
                    chosen_temp = ranked_item.temperature_used
                    chosen_check_pass = bool(ranked_item.check_pass)
                    chosen_text = ranked_item.patched_text
                    break

        round_record: dict[str, Any] = {
            "round": round_num,
            "mode": ROUTED_MODE,
            "selected_representation_mode": selected_representation_mode,
            "feedback_stage": feedback_stage,
            "feedback_output_length": len(feedback_output),
            "num_candidates": NUM_CANDIDATES,
            "representation_enabled": selected_representation_mode != "baseline-c5",
            "representation_char_count": len(context_text),
            "representation_selected_variable_count": len(
                context_obj.get("selected_variables", [])
                if isinstance(context_obj, dict)
                else []
            ),
            "representation_block_count": (
                int(context_obj.get("block_count", 0))
                if isinstance(context_obj, dict)
                else 0
            ),
            "ranked": [item.to_dict() for item in ranked],
            "simulate_attempts": simulate_attempts,
            "coverage_check_pass": coverage_check,
            "any_check_pass": coverage_check > 0,
            "coverage_simulate_pass": coverage_simulate,
            "any_simulate_pass": coverage_simulate > 0,
            "top_candidate_id": top.candidate_id if top else None,
            "top_check_pass": top.check_pass if top else False,
            "top_score": top.score if (top and top.score != float("-inf")) else None,
            "top_temperature": top.temperature_used if top else None,
            "chosen_candidate_id": chosen_id,
            "chosen_temperature": chosen_temp,
            "chosen_check_pass": chosen_check_pass,
            "chosen_simulate_pass": chosen_simulate_pass,
        }

        if chosen_text is None or chosen_text.strip() == current_text.strip():
            round_record["advance"] = "stalled_no_change"
            rounds.append(round_record)
            print(
                f"    -> STALLED at round {round_num} "
                f"(route={selected_representation_mode}, "
                f"coverage_check={coverage_check}/{NUM_CANDIDATES})"
            )
            break

        current_text = chosen_text
        if chosen_simulate_pass:
            final_pass = True
            final_round = round_num
            round_record["advance"] = "pass"
            rounds.append(round_record)
            print(
                f"    -> PASS at round {round_num} "
                f"(route={selected_representation_mode}, cand {chosen_id}, "
                f"coverage_sim={coverage_simulate}/{coverage_check})"
            )
            break
        if coverage_check > 0:
            round_record["advance"] = "check_pass_sim_fail_all"
        else:
            round_record["advance"] = "advanced_with_top"
        rounds.append(round_record)

    if not final_pass:
        print(f"    -> FAIL after {len(rounds)} round(s)")

    result = {
        "candidate_id": candidate_id,
        "mode": ROUTED_MODE,
        "num_candidates_per_round": NUM_CANDIDATES,
        "model_name": model_name,
        "final_status": "pass" if final_pass else "fail",
        "final_round": final_round,
        "round_count": len(rounds),
        "rounds": rounds,
    }
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="v0.19.56 representation routing runner")
    parser.add_argument("--cases", nargs="+", default=ALL_HARD_CASES)
    parser.add_argument("--planner-backend", default="gemini")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--oracle-existing-only", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    oracle_summary = build_oracle_existing_summary()
    (args.out_dir / "summary_oracle-existing.json").write_text(
        json.dumps(oracle_summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("=== ORACLE EXISTING UPPER BOUND ===")
    print(
        f"Pass: {oracle_summary['pass_count']}/{oracle_summary['case_count']} "
        f"({oracle_summary['pass_rate'] * 100.0:.1f}%)"
    )
    if args.oracle_existing_only:
        return

    print("\n=== REPRESENTATION ROUTING TRAJECTORY v0.19.56 ===")
    print(f"Mode: {ROUTED_MODE} (N={NUM_CANDIDATES})")
    print(f"Cases: {len(args.cases)}")
    print(f"Planner backend: {args.planner_backend}")
    print(f"Out: {args.out_dir}\n")

    results: list[dict[str, Any]] = []
    for candidate_id in args.cases:
        try:
            results.append(
                _run_single_case(
                    candidate_id=candidate_id,
                    out_dir=args.out_dir,
                    planner_backend=args.planner_backend,
                    skip_existing=args.skip_existing,
                )
            )
        except Exception as exc:
            print(f"  ERROR on {candidate_id}: {exc}")
            results.append(
                {"candidate_id": candidate_id, "mode": ROUTED_MODE, "error": str(exc)}
            )

    summary = compute_summary(ROUTED_MODE, results)
    summary["oracle_existing"] = oracle_summary
    summary_path = args.out_dir / f"summary_{ROUTED_MODE}.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n=== SUMMARY ({ROUTED_MODE}) ===")
    print(f"Total: {summary['case_count']}")
    print(f"Pass:  {summary['pass_count']} ({summary['pass_rate'] * 100.0:.1f}%)")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
