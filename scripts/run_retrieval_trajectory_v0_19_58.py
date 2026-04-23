"""A/B experiment for retrieval-augmented repair (v0.19.58).

Arms:
  - baseline-c5
  - retrieval-c5

Only the retrieval context block changes. Sampling, ranking, and OMC
validation stay identical across arms.
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
from gateforge.agent_modelica_retrieval_context_v0_19_58 import (  # noqa: E402
    build_retrieval_context,
)
from gateforge.agent_modelica_trajectory_store_v1 import load_trajectory_store  # noqa: E402
from gateforge.experiment_runner_shared import (  # noqa: E402
    ALL_HARD_CASES,
    MAX_ROUNDS,
    choose_candidate,
    compute_summary_core,
    load_broken_model,
    load_case_info,
    run_check_and_simulate_omc,
    run_check_only_omc,
)

MODE_TO_N = {
    "baseline-c5": 5,
    "retrieval-c5": 5,
}

COLD_CASES = [
    "v01945_ExciterAVR_v0_pp_e1_e2_pv_verr",
    "v01945_HydroTurbineGov_v0_pp_at_dturb_pv_speed",
    "v01945_SyncMachineSimplified_v0_pp_efd_set_id_set_pv_xadifd",
    "v01945_ExciterAVR_v0_pp_ta__pv_eterm+ve",
    "v01945_HydroTurbineGov_v0_pp_r__pv_pmech0+q",
    "v01945_ThermalZone_v0_pp_c1__pv_phi2+phi",
]


def _resolve_cases(dataset: str, custom_cases: list[str] | None) -> list[str]:
    if custom_cases:
        return custom_cases
    if dataset == "hot":
        return list(ALL_HARD_CASES)
    if dataset == "cold":
        return list(COLD_CASES)
    raise ValueError(f"unsupported dataset: {dataset}")


def _run_single_case(
    *,
    candidate_id: str,
    mode: str,
    out_dir: Path,
    planner_backend: str,
    store: dict | None,
    top_k: int,
    dataset: str,
    skip_existing: bool = False,
) -> dict:
    out_path = out_dir / f"{candidate_id}_{mode}.json"
    if skip_existing and out_path.exists():
        return json.loads(out_path.read_text(encoding="utf-8"))

    num_candidates = MODE_TO_N[mode]
    print(f"  [{dataset}/{mode}/N={num_candidates}] {candidate_id}")
    case_info = load_case_info(candidate_id)
    current_text = load_broken_model(candidate_id)
    model_name = case_info.get("model_name", candidate_id.split("_")[1] + "_v0")
    workflow_goal = case_info.get("workflow_goal", "")

    rounds: list[dict] = []
    final_pass = False
    final_round = 0

    for round_num in range(1, MAX_ROUNDS + 1):
        cur_check_ok, cur_omc_output = run_check_only_omc(
            current_text,
            model_name,
            workspace_prefix="gf_v01958_chk_",
        )
        if cur_check_ok:
            chk, sim, _ = run_check_and_simulate_omc(
                current_text,
                model_name,
                workspace_prefix="gf_v01958_sim_",
            )
            if chk and sim:
                final_pass = True
                final_round = round_num - 1 if round_num > 1 else 0
                print(f"    -> PASS (already passes check at round {round_num})")
                break

        retrieval_meta = {
            "retrieval_enabled": False,
            "retrieval_latency_ms": 0.0,
            "retrieval_hit_count": 0,
            "retrieval_context_char_count": 0,
            "retrieved_candidate_ids": [],
        }
        context_text = ""
        context_label = "Historical successful trajectory context"
        if mode == "retrieval-c5":
            retrieval_meta = build_retrieval_context(
                store=store or {},
                candidate_id=candidate_id,
                mode=mode,
                omc_output=cur_omc_output,
                round_num=round_num,
                top_k=top_k,
            )
            context_text = str(retrieval_meta.get("context_text") or "")
            context_label = str(retrieval_meta.get("context_label") or context_label)

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
            context_block=context_text,
            context_block_label=context_label,
        )

        def _runner(text: str) -> tuple[bool, str]:
            return run_check_only_omc(
                text,
                model_name,
                workspace_prefix="gf_v01958_chk_",
            )

        ranked = rank_candidates(candidates, run_omc=_runner)
        coverage_check = sum(1 for row in ranked if row.check_pass)
        top = ranked[0] if ranked else None

        simulate_attempts: list[dict] = []
        for row in ranked:
            if not row.check_pass:
                break
            if not row.patched_text:
                continue
            chk, sim, _ = run_check_and_simulate_omc(
                row.patched_text,
                model_name,
                workspace_prefix="gf_v01958_sim_",
            )
            simulate_attempts.append(
                {
                    "candidate_id": row.candidate_id,
                    "temperature_used": row.temperature_used,
                    "check_pass_again": bool(chk),
                    "simulate_pass": bool(sim),
                }
            )
        coverage_simulate = sum(1 for row in simulate_attempts if row["simulate_pass"])

        (
            chosen_id,
            chosen_temp,
            chosen_text,
            chosen_check_pass,
            chosen_simulate_pass,
        ) = choose_candidate(ranked, simulate_attempts)

        round_record = {
            "round": round_num,
            "dataset": dataset,
            "mode": mode,
            "num_candidates": num_candidates,
            "retrieval_enabled": mode == "retrieval-c5",
            "retrieval_latency_ms": float(retrieval_meta.get("retrieval_latency_ms") or 0.0),
            "retrieval_hit_count": int(retrieval_meta.get("retrieved_hit_count") or 0),
            "retrieval_context_char_count": len(context_text),
            "retrieved_candidate_ids": [
                str(hit.get("candidate_id") or "")
                for hit in (retrieval_meta.get("retrieved_hits") or [])
                if isinstance(hit, dict)
            ],
            "ranked": [row.to_dict() for row in ranked],
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
        "dataset": dataset,
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


def compute_summary(mode: str, dataset: str, results: list[dict]) -> dict:
    summary = compute_summary_core(mode, results)
    valid = [row for row in results if not row.get("error")]
    latencies = []
    hit_counts = []
    context_chars = []
    for result in valid:
        for rd in result.get("rounds", []):
            if rd.get("retrieval_enabled"):
                latencies.append(float(rd.get("retrieval_latency_ms") or 0.0))
                hit_counts.append(int(rd.get("retrieval_hit_count") or 0))
                context_chars.append(int(rd.get("retrieval_context_char_count") or 0))
    summary["dataset"] = dataset
    summary["avg_retrieval_latency_ms"] = sum(latencies) / len(latencies) if latencies else 0.0
    summary["avg_retrieval_hit_count"] = sum(hit_counts) / len(hit_counts) if hit_counts else 0.0
    summary["avg_retrieval_context_chars"] = sum(context_chars) / len(context_chars) if context_chars else 0.0
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="A/B experiment for retrieval-augmented repair")
    parser.add_argument("--mode", choices=list(MODE_TO_N.keys()), required=True)
    parser.add_argument("--dataset", choices=["hot", "cold"], default="hot")
    parser.add_argument("--cases", nargs="+", default=None)
    parser.add_argument("--planner-backend", default="gemini")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--store-path",
        type=Path,
        default=REPO_ROOT / "artifacts" / "trajectory_store_v0_19_57" / "store.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "artifacts" / "retrieval_trajectory_v0_19_58",
    )
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    cases = _resolve_cases(args.dataset, args.cases)
    out_dir = args.out_dir / args.dataset / args.mode
    out_dir.mkdir(parents=True, exist_ok=True)
    store = load_trajectory_store(args.store_path) if args.mode == "retrieval-c5" else None

    results = []
    for candidate_id in cases:
        try:
            result = _run_single_case(
                candidate_id=candidate_id,
                mode=args.mode,
                out_dir=out_dir,
                planner_backend=args.planner_backend,
                store=store,
                top_k=args.top_k,
                dataset=args.dataset,
                skip_existing=args.skip_existing,
            )
        except Exception as exc:
            result = {
                "candidate_id": candidate_id,
                "dataset": args.dataset,
                "mode": args.mode,
                "error": str(exc),
            }
        results.append(result)

    summary = compute_summary(args.mode, args.dataset, results)
    summary["cases"] = cases
    summary["top_k"] = int(args.top_k)
    summary["store_path"] = str(args.store_path)
    summary["planner_backend"] = str(args.planner_backend)
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
