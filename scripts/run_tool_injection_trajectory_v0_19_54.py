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
from gateforge.agent_modelica_omc_workspace_v1 import (  # noqa: E402
    extract_om_success_flags,
    prepare_workspace_model_layout,
    run_check_and_simulate,
    run_omc_script_docker,
    temporary_workspace,
)
from gateforge.agent_modelica_tool_context_v1 import (  # noqa: E402
    build_modelica_query_tool_context,
    format_modelica_query_tool_context,
)

DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
MAX_ROUNDS = 4

STALLED_CASES = [
    "v01945_ExciterAVR_v0_pp_e1_e2_pv_se_efd",
    "v01945_HydroTurbineGov_v0_pp_at_dturb_pv_q_nl",
    "v01945_SyncMachineSimplified_v0_pp_efd_set_id_set_pv_psippq",
    "v01945_ThermalZone_v0_pp_c1_c2_pv_phi1",
    "v01945_ThermalZone_v0_pp_c1_c3_pv_phi1",
]
HINT_RESISTANT_CASES = [
    "v01945_HydroTurbineGov_v0_pp_r__pv_pmech0+p",
    "v01945_SyncMachineSimplified_v0_pp_tpd0__pv_efd+id",
    "v01945_SyncMachineSimplified_v0_pp_tpd0__pv_psippd+p",
]
ALL_HARD_CASES = STALLED_CASES + HINT_RESISTANT_CASES

MODE_TO_N = {
    "baseline-c5": 5,
    "tool-c5": 5,
}


def _load_case_info(candidate_id: str) -> dict:
    for path in [
        REPO_ROOT / "artifacts" / "triple_underdetermined_experiment_v0_19_45_pp_pv_pv" / "admitted_cases.jsonl",
        REPO_ROOT / "artifacts" / "triple_underdetermined_experiment_v0_19_45" / "admitted_cases.jsonl",
    ]:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    if row.get("candidate_id") == candidate_id:
                        return row
    raise FileNotFoundError(f"Case info not found for {candidate_id}")


def _load_broken_model(candidate_id: str) -> str:
    for sub in [
        "triple_underdetermined_experiment_v0_19_45_pp_pv_pv",
        "triple_underdetermined_experiment_v0_19_45",
    ]:
        path = REPO_ROOT / "artifacts" / sub / f"{candidate_id}.mo"
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Broken model not found for {candidate_id}")


def _run_check_only(model_text: str, model_name: str) -> tuple[bool, str]:
    """Run only OMC checkModel for ranking and repair feedback."""
    with temporary_workspace("gf_v01954_chk_") as ws:
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
        load_lines = "".join(
            f'loadFile("{item}");\n'
            for item in layout.model_load_files
            if str(item or "").strip()
        )
        script = (
            "loadModel(Modelica);\n"
            + load_lines
            + f"checkModel({layout.model_identifier});\n"
            + "getErrorString();\n"
        )
        _, output = run_omc_script_docker(
            script, timeout_sec=180, cwd=str(workspace), image=DOCKER_IMAGE
        )
        check_ok, _ = extract_om_success_flags(output)
        return bool(check_ok), str(output or "")


def _run_check_and_simulate(model_text: str, model_name: str) -> tuple[bool, bool, str]:
    """Run full checkModel + simulate for final candidate validation."""
    with temporary_workspace("gf_v01954_sim_") as ws:
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
        _, output, check_ok, simulate_ok = run_check_and_simulate(
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
        return bool(check_ok), bool(simulate_ok), str(output or "")


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

    case_info = _load_case_info(candidate_id)
    current_text = _load_broken_model(candidate_id)
    model_name = case_info.get("model_name", candidate_id.split("_")[1] + "_v0")
    workflow_goal = case_info.get("workflow_goal", "")

    rounds: list[dict] = []
    final_pass = False
    final_round = 0

    for round_num in range(1, MAX_ROUNDS + 1):
        cur_check_ok, cur_omc_output = _run_check_only(current_text, model_name)
        if cur_check_ok:
            chk, sim, _ = _run_check_and_simulate(current_text, model_name)
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
            return _run_check_only(text, model_name)

        ranked = rank_candidates(candidates, run_omc=_runner)
        coverage_check = sum(1 for r in ranked if r.check_pass)
        top = ranked[0] if ranked else None

        simulate_attempts: list[dict] = []
        for r in ranked:
            if not r.check_pass:
                break
            if not r.patched_text:
                continue
            chk, sim, _ = _run_check_and_simulate(r.patched_text, model_name)
            simulate_attempts.append(
                {
                    "candidate_id": r.candidate_id,
                    "temperature_used": r.temperature_used,
                    "check_pass_again": bool(chk),
                    "simulate_pass": bool(sim),
                }
            )
        coverage_simulate = sum(1 for s in simulate_attempts if s["simulate_pass"])

        chosen_id: int | None = None
        chosen_temp: float | None = None
        chosen_text: str | None = None
        chosen_check_pass = False
        chosen_simulate_pass = False

        for s in simulate_attempts:
            if s["simulate_pass"]:
                chosen_id = s["candidate_id"]
                chosen_temp = s["temperature_used"]
                chosen_simulate_pass = True
                chosen_check_pass = True
                for r in ranked:
                    if r.candidate_id == chosen_id:
                        chosen_text = r.patched_text
                        break
                break

        if chosen_id is None:
            for r in ranked:
                if r.patched_text:
                    chosen_id = r.candidate_id
                    chosen_temp = r.temperature_used
                    chosen_check_pass = bool(r.check_pass)
                    chosen_text = r.patched_text
                    break

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
    valid = [r for r in results if not r.get("error")]
    passes = sum(1 for r in valid if r.get("final_status") == "pass")
    total_rounds = 0
    total_any_check = 0
    total_any_sim = 0
    total_candidates = 0
    total_check_pass_candidates = 0
    total_sim_pass_candidates = 0
    tool_context_chars = []
    tool_selected_counts = []

    for result in valid:
        for rd in result.get("rounds", []):
            total_rounds += 1
            n = int(rd.get("num_candidates") or 0)
            total_candidates += n
            if rd.get("any_check_pass"):
                total_any_check += 1
            if rd.get("any_simulate_pass"):
                total_any_sim += 1
            total_check_pass_candidates += int(rd.get("coverage_check_pass") or 0)
            total_sim_pass_candidates += int(rd.get("coverage_simulate_pass") or 0)
            if rd.get("tool_context_enabled"):
                tool_context_chars.append(int(rd.get("tool_context_char_count") or 0))
                tool_selected_counts.append(int(rd.get("tool_selected_variable_count") or 0))

    return {
        "mode": mode,
        "case_count": len(valid),
        "pass_count": passes,
        "pass_rate": passes / len(valid) if valid else 0.0,
        "round_count": total_rounds,
        "per_round_any_check_pass": {
            "count": total_any_check,
            "denominator": total_rounds,
            "rate": total_any_check / total_rounds if total_rounds else 0.0,
        },
        "per_round_any_simulate_pass": {
            "count": total_any_sim,
            "denominator": total_rounds,
            "rate": total_any_sim / total_rounds if total_rounds else 0.0,
        },
        "pooled_candidate_check_pass": {
            "count": total_check_pass_candidates,
            "denominator": total_candidates,
            "rate": (
                total_check_pass_candidates / total_candidates
                if total_candidates
                else 0.0
            ),
        },
        "pooled_candidate_simulate_pass": {
            "count": total_sim_pass_candidates,
            "denominator": total_candidates,
            "rate": (
                total_sim_pass_candidates / total_candidates
                if total_candidates
                else 0.0
            ),
        },
        "avg_tool_context_chars": (
            sum(tool_context_chars) / len(tool_context_chars)
            if tool_context_chars
            else 0.0
        ),
        "avg_tool_selected_variable_count": (
            sum(tool_selected_counts) / len(tool_selected_counts)
            if tool_selected_counts
            else 0.0
        ),
        "cases": [
            {
                "candidate_id": r.get("candidate_id"),
                "final_status": r.get("final_status"),
                "round_count": r.get("round_count"),
            }
            for r in valid
        ],
    }


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

