"""A/B experiment: no domain knowledge vs Modelica parameter semantics injection.

v0.19.50 discipline:
  - Identical prompt structure, model, temperature, LLM
  - Only difference: domain_knowledge is empty vs populated with Modelica
    parameter/variable semantics targeting type_b1 and type_b2 failure modes
  - Runs on the 5 stalled + 3 hint-resistant cases from v0.19.47

Usage:
  python3 scripts/run_domain_knowledge_experiment_v0_19_50.py --mode baseline
  python3 scripts/run_domain_knowledge_experiment_v0_19_50.py --mode domain_knowledge
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

os.environ.setdefault("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN", "120")
os.environ.setdefault("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", "180")

from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text
from gateforge.agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)
from scripts.triple_attribution_v0_19_45 import compute_states

DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
PLANNER_BACKEND = "gemini"
MAX_ROUNDS = 4

# Domain knowledge targeting type_b1 (wrong direction) and type_b2 (incomplete cleanup)
MODELICA_PARAMETER_SEMANTICS = (
    "Modelica variable semantics for underconstrained repair: "
    "(1) `parameter Real X = value;` is a parameter binding — it makes X a fixed constant "
    "with both type and value in the declarations section. "
    "If the broken model has `Real X;` (a continuous variable) where the source had "
    "`parameter Real X = value;`, the CORRECT fix is to restore `parameter Real X = value;` "
    "in the variable declarations. Do NOT add `X = value;` in the equation section — "
    "that creates a continuous equation, not a parameter binding, and is WRONG. "
    "(2) If there is a `Real X_phantom;` declaration whose name does not appear in any equation "
    "as the solved variable, the CORRECT fix is: DELETE the `Real X_phantom;` declaration AND "
    "replace all references to `X_phantom` in equations with the original variable name. "
    "Leaving the orphan declaration while only fixing references is an INCOMPLETE repair."
)

# Hard case sources: 5 stalled + 3 hint-resistant from v0.19.47
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
    path = REPO_ROOT / "artifacts" / "triple_underdetermined_experiment_v0_19_45_pp_pv_pv" / f"{candidate_id}.mo"
    if not path.exists():
        path = REPO_ROOT / "artifacts" / "triple_underdetermined_experiment_v0_19_45" / f"{candidate_id}.mo"
    if not path.exists():
        raise FileNotFoundError(f"Broken model not found for {candidate_id}")
    return path.read_text(encoding="utf-8")


def _run_check_and_simulate(model_text: str, model_name: str) -> tuple[bool, bool, str]:
    with temporary_workspace("gf_v01950_dk_") as ws:
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


def _llm_turn(
    *,
    model_text: str,
    model_name: str,
    omc_output: str,
    current_round: int,
    mode: str,
    workflow_goal: str = "",
) -> tuple[str | None, str, str]:
    domain_knowledge = MODELICA_PARAMETER_SEMANTICS if mode == "domain_knowledge" else ""
    patched, err, provider = llm_repair_model_text(
        planner_backend=PLANNER_BACKEND,
        original_text=model_text,
        failure_type="underconstrained_system",
        expected_stage="check",
        error_excerpt=omc_output[:12000],
        repair_actions=[],
        model_name=model_name,
        workflow_goal=workflow_goal,
        current_round=current_round,
        domain_knowledge=domain_knowledge,
    )
    return patched, err, provider


def _run_single_case(
    candidate_id: str,
    mode: str,
    out_dir: Path,
) -> dict:
    print(f"  [{mode}] Running {candidate_id}...")

    case_info = _load_case_info(candidate_id)
    broken_text = _load_broken_model(candidate_id)
    model_name = case_info.get("model_name", candidate_id.split("_")[1] + "_v0")
    workflow_goal = case_info.get("workflow_goal", "")
    source_text = ""
    src_path = Path(case_info.get("source_model_path", ""))
    if src_path.exists():
        source_text = src_path.read_text(encoding="utf-8")

    pp1_target = case_info.get("pp1_target", "")
    pp2_target = case_info.get("pp2_target", "")
    pv_target = case_info.get("pv_target", "")
    pv_base_var = case_info.get("pv_base_var", "")

    attempts: list[dict] = []
    current_text = broken_text
    final_pass = False

    for round_num in range(1, MAX_ROUNDS + 1):
        check_ok, simulate_ok, omc_output = _run_check_and_simulate(current_text, model_name)

        before = compute_states(
            current_text, pp1_target, pp2_target, pv_target, pv_base_var,
            source_text, check_ok, simulate_ok,
        )

        patched, llm_err, provider = _llm_turn(
            model_text=current_text,
            model_name=model_name,
            omc_output=omc_output,
            current_round=round_num,
            mode=mode,
            workflow_goal=workflow_goal,
        )

        model_changed = patched is not None and patched.strip() != current_text.strip()

        if patched and model_changed:
            current_text = patched
            check_ok_after, simulate_ok_after, omc_output_after = _run_check_and_simulate(
                current_text, model_name
            )
        else:
            check_ok_after, simulate_ok_after, omc_output_after = check_ok, simulate_ok, omc_output

        after = compute_states(
            current_text, pp1_target, pp2_target, pv_target, pv_base_var,
            source_text, check_ok_after, simulate_ok_after,
        )

        attempt = {
            "round": round_num,
            "check_pass_before_patch": check_ok,
            "simulate_pass_before_patch": simulate_ok,
            "omc_output_before_patch": omc_output,
            "patched_text_present": patched is not None,
            "model_changed": model_changed,
            "provider": provider,
            "llm_error": llm_err,
            "check_pass_after_patch": check_ok_after,
            "simulate_pass_after_patch": simulate_ok_after,
            "omc_output_after_patch": omc_output_after,
            "pp1_state_before": before["pp1"],
            "pp2_state_before": before["pp2"],
            "pv_state_before": before["pv"],
            "pp1_state_after": after["pp1"],
            "pp2_state_after": after["pp2"],
            "pv_state_after": after["pv"],
            "domain_knowledge_mode": mode,
        }
        attempts.append(attempt)

        if check_ok_after and simulate_ok_after:
            final_pass = True
            print(f"    -> PASS at round {round_num}")
            break

        if not model_changed:
            print(f"    -> STALLED at round {round_num}")
            break

    if not final_pass and attempts and attempts[-1].get("model_changed"):
        print(f"    -> MAX ROUNDS reached")

    result = {
        "candidate_id": candidate_id,
        "mode": mode,
        "model_name": model_name,
        "final_status": "pass" if final_pass else "fail",
        "turn_count": len(attempts),
        "attempts": attempts,
    }

    out_path = out_dir / f"{candidate_id}_{mode}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="A/B experiment: baseline vs Modelica domain knowledge injection")
    parser.add_argument("--mode", choices=["baseline", "domain_knowledge"], required=True)
    parser.add_argument("--cases", nargs="+", default=ALL_HARD_CASES, help="Specific case IDs to run")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "artifacts" / "domain_knowledge_experiment_v0_19_50")
    args = parser.parse_args()

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== DOMAIN KNOWLEDGE EXPERIMENT v0.19.50 ===")
    print(f"Mode: {args.mode}")
    print(f"Cases: {len(args.cases)}")
    print(f"Output: {out_dir}")
    if args.mode == "domain_knowledge":
        print(f"Knowledge: {MODELICA_PARAMETER_SEMANTICS[:80]}...")
    print()

    results: list[dict] = []
    for cid in args.cases:
        try:
            result = _run_single_case(cid, args.mode, out_dir)
            results.append(result)
        except Exception as exc:
            print(f"  ERROR on {cid}: {exc}")
            results.append({"candidate_id": cid, "mode": args.mode, "error": str(exc)})

    passes = sum(1 for r in results if r.get("final_status") == "pass")
    print(f"\n=== SUMMARY ({args.mode}) ===")
    print(f"Total: {len(results)}")
    print(f"Pass: {passes}")
    print(f"Fail: {len(results) - passes}")
    for r in results:
        status = r.get("final_status", "error")
        turns = r.get("turn_count", "N/A")
        print(f"  {r['candidate_id']}: {status} ({turns} turns)")


if __name__ == "__main__":
    main()
