"""A/B experiment: single-candidate baseline vs multi-candidate sampling + OMC residual ranking.

v0.19.51 discipline:
  - Identical prompt structure, model, LLM, max_rounds
  - Only difference: num_candidates per round (1 vs 3 vs 5) + temperature schedule
  - Ranker uses ONLY structural OMC signals (check_pass, deficit, error_count)
  - Ranker is pure: no heuristic patching, no LLM, no domain knowledge
  - Runs on the same 8 hard cases as v0.19.49 / v0.19.50

Usage:
  python3 scripts/run_multi_candidate_trajectory_v0_19_51.py --mode baseline
  python3 scripts/run_multi_candidate_trajectory_v0_19_51.py --mode multi-c3
  python3 scripts/run_multi_candidate_trajectory_v0_19_51.py --mode multi-c5

Mode → num_candidates:
  baseline  → 1
  multi-c3  → 3
  multi-c5  → 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN", "240")
os.environ.setdefault("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", "180")

from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text_multi
from gateforge.agent_modelica_candidate_ranker_v1 import rank_candidates
from gateforge.experiment_runner_shared import (
    ALL_HARD_CASES,
    MAX_ROUNDS,
    load_broken_model,
    load_case_info,
    run_check_and_simulate_omc,
    run_check_only_omc,
    choose_candidate,
)

PLANNER_BACKEND = "gemini"

MODE_TO_N = {
    "baseline": 1,
    "multi-c3": 3,
    "multi-c5": 5,
}


def _run_single_case(
    candidate_id: str,
    mode: str,
    out_dir: Path,
) -> dict:
    """Run one hard case for up to MAX_ROUNDS, sampling N candidates per round."""
    num_candidates = MODE_TO_N[mode]
    print(f"  [{mode}/N={num_candidates}] {candidate_id}")

    case_info = load_case_info(candidate_id)
    broken_text = load_broken_model(candidate_id)
    model_name = case_info.get("model_name", candidate_id.split("_")[1] + "_v0")
    workflow_goal = case_info.get("workflow_goal", "")

    rounds: list[dict] = []
    current_text = broken_text
    final_pass = False
    final_round = 0

    for round_num in range(1, MAX_ROUNDS + 1):
        # Probe current state once (used as the LLM error_excerpt input)
        cur_check_ok, cur_omc_output = run_check_only_omc(current_text, model_name, workspace_prefix="gf_v01951_chk_")
        if cur_check_ok:
            # Already passes check — confirm with simulate
            chk, sim, _ = run_check_and_simulate_omc(current_text, model_name, workspace_prefix="gf_v01951_sim_")
            if chk and sim:
                final_pass = True
                final_round = round_num - 1 if round_num > 1 else 0
                print(f"    -> PASS (already passes check at round {round_num})")
                break

        # Sample N candidates
        candidates = llm_repair_model_text_multi(
            planner_backend=PLANNER_BACKEND,
            original_text=current_text,
            failure_type="underconstrained_system",
            expected_stage="check",
            error_excerpt=cur_omc_output[:12000],
            repair_actions=[],
            model_name=model_name,
            workflow_goal=workflow_goal,
            current_round=round_num,
            num_candidates=num_candidates,
        )

        # Rank using check-only OMC residual signals
        def _runner(text: str) -> tuple[bool, str]:
            return run_check_only_omc(text, model_name, workspace_prefix="gf_v01951_chk_")

        ranked = rank_candidates(candidates, run_omc=_runner)
        ranked_dicts = [r.to_dict() for r in ranked]
        coverage_check = sum(1 for r in ranked if r.check_pass)
        top = ranked[0] if ranked else None

        # Run simulate on EVERY check_pass candidate so coverage@K at simulate
        # level is observable. Ranker is sorted by score desc and check_pass
        # candidates always score above non-check-pass ones, so we can stop
        # iterating at the first non-check-pass entry.
        # Do NOT short-circuit on the first simulate_pass either: the whole
        # point of multi-candidate sampling is to measure how many of K
        # samples reach simulate_pass, not just whether one did. An
        # early-stop optimization here would silently destroy the
        # coverage_simulate@K signal we need for the v0.19.51 A/B.
        simulate_attempts: list[dict] = []
        for r in ranked:
            if not r.check_pass:
                break
            if not r.patched_text:
                continue
            chk, sim, _ = run_check_and_simulate_omc(r.patched_text, model_name, workspace_prefix="gf_v01951_sim_")
            simulate_attempts.append({
                "candidate_id": r.candidate_id,
                "temperature_used": r.temperature_used,
                "check_pass_again": bool(chk),
                "simulate_pass": bool(sim),
            })
        coverage_simulate = sum(1 for s in simulate_attempts if s["simulate_pass"])

        # Choose advance candidate:
        #  1. first simulate_pass; else
        #  2. first ranked candidate with patched_text (top check_pass if any,
        #     otherwise top by score regardless of check_pass)
        (
            chosen_id,
            chosen_temp,
            chosen_text,
            chosen_check_pass,
            chosen_simulate_pass,
        ) = choose_candidate(ranked, simulate_attempts)

        round_record = {
            "round": round_num,
            "num_candidates": num_candidates,
            "ranked": ranked_dicts,
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
                f"(coverage_check={coverage_check}/{num_candidates})"
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
                f"(cand {chosen_id}, T={chosen_temp}, "
                f"coverage_sim={coverage_simulate}/{coverage_check})"
            )
            break
        elif coverage_check > 0:
            round_record["advance"] = "check_pass_sim_fail_all"
        else:
            round_record["advance"] = "advanced_with_top"

        rounds.append(round_record)

    if not final_pass:
        print(f"    -> FAIL after {len(rounds)} round(s)")

    result = {
        "candidate_id": candidate_id,
        "mode": mode,
        "num_candidates_per_round": num_candidates,
        "model_name": model_name,
        "final_status": "pass" if final_pass else "fail",
        "final_round": final_round,
        "round_count": len(rounds),
        "rounds": rounds,
    }

    out_path = out_dir / f"{candidate_id}_{mode}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def _print_summary(mode: str, results: list[dict]) -> None:
    passes = sum(1 for r in results if r.get("final_status") == "pass")
    n = len(results)
    print(f"\n=== SUMMARY ({mode}) ===")
    print(f"Total: {n}")
    print(f"Pass:  {passes} ({100.0*passes/max(n,1):.1f}%)")
    print(f"Fail:  {n - passes}")
    # Coverage@K aggregates
    total_rounds = 0
    total_any_check = 0
    total_any_sim = 0
    for r in results:
        for rd in r.get("rounds", []):
            total_rounds += 1
            if rd.get("any_check_pass"):
                total_any_check += 1
            if rd.get("any_simulate_pass"):
                total_any_sim += 1
    if total_rounds:
        print(
            f"Per-round any_check_pass:    {total_any_check}/{total_rounds} "
            f"({100.0*total_any_check/total_rounds:.1f}%)"
        )
        print(
            f"Per-round any_simulate_pass: {total_any_sim}/{total_rounds} "
            f"({100.0*total_any_sim/total_rounds:.1f}%)"
        )
    for r in results:
        print(
            f"  {r['candidate_id']}: {r.get('final_status', 'error')} "
            f"({r.get('round_count', 'N/A')} rounds)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="A/B experiment: single vs multi-candidate sampling + OMC residual ranking"
    )
    parser.add_argument("--mode", choices=list(MODE_TO_N.keys()), required=True)
    parser.add_argument("--cases", nargs="+", default=ALL_HARD_CASES)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "artifacts" / "multi_candidate_trajectory_v0_19_51",
    )
    args = parser.parse_args()

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== MULTI-CANDIDATE TRAJECTORY EXPERIMENT v0.19.51 ===")
    print(f"Mode:  {args.mode}  (N={MODE_TO_N[args.mode]} candidates / round)")
    print(f"Cases: {len(args.cases)}")
    print(f"Out:   {out_dir}")
    print()

    results: list[dict] = []
    for cid in args.cases:
        try:
            result = _run_single_case(cid, args.mode, out_dir)
            results.append(result)
        except Exception as exc:
            print(f"  ERROR on {cid}: {exc}")
            results.append({"candidate_id": cid, "mode": args.mode, "error": str(exc)})

    _print_summary(args.mode, results)


if __name__ == "__main__":
    main()
