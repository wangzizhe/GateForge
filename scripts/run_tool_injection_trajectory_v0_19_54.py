"""A/B experiment: multi-candidate baseline vs Modelica query tool observations.

v0.19.54 discipline:
  - Baseline is equivalent to v0.19.51 multi-c5.
  - Tool arm injects query-tool observations as facts only.
  - No executor changes, no repair hints, no deterministic patching.

Usage:
  python3 scripts/run_tool_injection_trajectory_v0_19_54.py --mode baseline-c5
  python3 scripts/run_tool_injection_trajectory_v0_19_54.py --mode tool-c5
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

from gateforge.agent_modelica_candidate_ranker_v1 import rank_candidates  # noqa: E402
from gateforge.agent_modelica_l2_plan_replan_engine_v1 import (  # noqa: E402
    llm_repair_model_text_multi,
)
from gateforge.agent_modelica_tool_context_v1 import (  # noqa: E402
    build_modelica_query_tool_context,
    format_modelica_query_tool_context,
)
from gateforge.experiment_runner_shared import (  # noqa: E402
    ALL_HARD_CASES,
    MAX_ROUNDS,
    load_broken_model,
    load_case_info,
    run_check_and_simulate_omc,
    run_check_only_omc,
    choose_candidate,
    compute_summary_core,
)

MODE_TO_N = {
    "baseline-c5": 5,
    "tool-c5": 5,
}


def _build_tool_context_for_round(
    *,
    mode: str,
    model_text: str,
    omc_output: str,
) -> tuple[str, dict]:
    if mode != "tool-c5":
        return "", {}
    context = build_modelica_query_tool_context(
        model_text=model_text,
        omc_output=omc_output,
    )
    return format_modelica_query_tool_context(context), context


def _run_single_case(
    *,
    candidate_id: str,
    mode: str,
    out_dir: Path,
    planner_backend: str,
    skip_existing: bool = False,
) -> dict:
    out_path = out_dir / f"{candidate_id}_{mode}.json"
    if skip_existing and out_path.exists():
        return json.loads(out_path.read_text(encoding="utf-8"))

    num_candidates = MODE_TO_N[mode]
    print(f"  [{mode}/N={num_candidates}] {candidate_id}")

    case_info = load_case_info(candidate_id)
    current_text = load_broken_model(candidate_id)
    model_name = case_info.get("model_name", candidate_id.split("_")[1] + "_v0")
    workflow_goal = case_info.get("workflow_goal", "")

    rounds: list[dict] = []
    final_pass = False
    final_round = 0

    for round_num in range(1, MAX_ROUNDS + 1):
        cur_check_ok, cur_omc_output = run_check_only_omc(current_text, model_name, workspace_prefix="gf_v01954_chk_")
        if cur_check_ok:
            chk, sim, _ = run_check_and_simulate_omc(current_text, model_name, workspace_prefix="gf_v01954_sim_")
            if chk and sim:
                final_pass = True
                final_round = round_num - 1 if round_num > 1 else 0
                print(f"    -> PASS (already passes check at round {round_num})")
                break

        tool_context_text, tool_context_obj = _build_tool_context_for_round(
            mode=mode,
            model_text=current_text,
            omc_output=cur_omc_output,
        )

        candidates = llm_repair_model_text_multi(
            planner_backend=planner_backend,
            original_text=current_text,
            failure_type="underconstrained_system",
            expected_stage="check",
            error_excerpt=cur_omc_output[:12000],
            repair_actions=[],
            model_name=model_name,
            workflow_goal=workflow_goal,
            current_round=round_num,
            num_candidates=num_candidates,
            tool_context=tool_context_text,
        )

        def _runner(text: str) -> tuple[bool, str]:
            return run_check_only_omc(text, model_name, workspace_prefix="gf_v01954_chk_")

        ranked = rank_candidates(candidates, run_omc=_runner)
        coverage_check = sum(1 for r in ranked if r.check_pass)
        top = ranked[0] if ranked else None

        simulate_attempts: list[dict] = []
        for r in ranked:
            if not r.check_pass:
                break
            if not r.patched_text:
                continue
            chk, sim, _ = run_check_and_simulate_omc(r.patched_text, model_name, workspace_prefix="gf_v01954_sim_")
            simulate_attempts.append(
                {
                    "candidate_id": r.candidate_id,
                    "temperature_used": r.temperature_used,
                    "check_pass_again": bool(chk),
                    "simulate_pass": bool(sim),
                }
            )
        coverage_simulate = sum(1 for s in simulate_attempts if s["simulate_pass"])

        (
            chosen_id,
            chosen_temp,
            chosen_text,
            chosen_check_pass,
            chosen_simulate_pass,
        ) = choose_candidate(ranked, simulate_attempts)

        round_record = {
            "round": round_num,
            "mode": mode,
            "num_candidates": num_candidates,
            "tool_context_enabled": mode == "tool-c5",
            "tool_context_char_count": len(tool_context_text),
            "tool_selected_variable_count": len(
                tool_context_obj.get("selected_variables", [])
                if isinstance(tool_context_obj, dict)
                else []
            ),
            "tool_selected_variables": (
                tool_context_obj.get("selected_variables", [])
                if isinstance(tool_context_obj, dict)
                else []
            ),
            "ranked": [r.to_dict() for r in ranked],
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
        if coverage_check > 0:
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
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def compute_summary(mode: str, results: list[dict]) -> dict:
    """Compute consistent v0.19.54 aggregate metrics for one arm."""
    summary = compute_summary_core(mode, results)
    valid = [r for r in results if not r.get("error")]
    tool_context_chars = []
    tool_selected_counts = []

    for result in valid:
        for rd in result.get("rounds", []):
            if rd.get("tool_context_enabled"):
                tool_context_chars.append(int(rd.get("tool_context_char_count") or 0))
                tool_selected_counts.append(int(rd.get("tool_selected_variable_count") or 0))

    summary["avg_tool_context_chars"] = (
        sum(tool_context_chars) / len(tool_context_chars)
        if tool_context_chars
        else 0.0
    )
    summary["avg_tool_selected_variable_count"] = (
        sum(tool_selected_counts) / len(tool_selected_counts)
        if tool_selected_counts
        else 0.0
    )
    summary["cases"] = [
        {
            "candidate_id": r.get("candidate_id"),
            "final_status": r.get("final_status"),
            "round_count": r.get("round_count"),
        }
        for r in valid
    ]
    return summary


def _print_summary(summary: dict) -> None:
    print(f"\n=== SUMMARY ({summary['mode']}) ===")
    print(f"Total: {summary['case_count']}")
    print(f"Pass:  {summary['pass_count']} ({summary['pass_rate'] * 100.0:.1f}%)")
    print(
        "Per-round any_check_pass: "
        f"{summary['per_round_any_check_pass']['count']}/"
        f"{summary['per_round_any_check_pass']['denominator']} "
        f"({summary['per_round_any_check_pass']['rate'] * 100.0:.1f}%)"
    )
    print(
        "Per-round any_simulate_pass: "
        f"{summary['per_round_any_simulate_pass']['count']}/"
        f"{summary['per_round_any_simulate_pass']['denominator']} "
        f"({summary['per_round_any_simulate_pass']['rate'] * 100.0:.1f}%)"
    )
    print(
        "Pooled candidate simulate_pass: "
        f"{summary['pooled_candidate_simulate_pass']['count']}/"
        f"{summary['pooled_candidate_simulate_pass']['denominator']} "
        f"({summary['pooled_candidate_simulate_pass']['rate'] * 100.0:.1f}%)"
    )
    if summary["avg_tool_context_chars"]:
        print(f"Avg tool context chars: {summary['avg_tool_context_chars']:.1f}")
        print(
            "Avg selected variables: "
            f"{summary['avg_tool_selected_variable_count']:.1f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v0.19.54 tool observation injection A/B runner"
    )
    parser.add_argument("--mode", choices=list(MODE_TO_N.keys()), required=True)
    parser.add_argument("--cases", nargs="+", default=ALL_HARD_CASES)
    parser.add_argument("--planner-backend", default="gemini")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "artifacts" / "tool_injection_trajectory_v0_19_54",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print("=== TOOL INJECTION TRAJECTORY EXPERIMENT v0.19.54 ===")
    print(f"Mode:  {args.mode}  (N={MODE_TO_N[args.mode]} candidates / round)")
    print(f"Cases: {len(args.cases)}")
    print(f"Planner backend: {args.planner_backend}")
    print(f"Out:   {args.out_dir}")
    print()

    results: list[dict] = []
    for cid in args.cases:
        try:
            results.append(
                _run_single_case(
                    candidate_id=cid,
                    mode=args.mode,
                    out_dir=args.out_dir,
                    planner_backend=args.planner_backend,
                    skip_existing=args.skip_existing,
                )
            )
        except Exception as exc:
            print(f"  ERROR on {cid}: {exc}")
            results.append({"candidate_id": cid, "mode": args.mode, "error": str(exc)})

    summary = compute_summary(args.mode, results)
    summary_path = args.out_dir / f"summary_{args.mode}.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _print_summary(summary)
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
