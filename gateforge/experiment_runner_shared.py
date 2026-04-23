"""Shared utilities for experiment runner scripts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateforge.agent_modelica_omc_workspace_v1 import (
    extract_om_success_flags,
    prepare_workspace_model_layout,
    run_check_and_simulate,
    run_omc_script_docker,
    temporary_workspace,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
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


def load_case_info(candidate_id: str) -> dict:
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


def load_broken_model(candidate_id: str) -> str:
    for sub in [
        "triple_underdetermined_experiment_v0_19_45_pp_pv_pv",
        "triple_underdetermined_experiment_v0_19_45",
    ]:
        path = REPO_ROOT / "artifacts" / sub / f"{candidate_id}.mo"
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Broken model not found for {candidate_id}")


def run_check_only_omc(
    model_text: str, model_name: str, workspace_prefix: str = "gf_chk_"
) -> tuple[bool, str]:
    """Run only OMC checkModel (no simulate) — cheaper for ranker.

    Returns (check_ok, raw_omc_output).
    """
    with temporary_workspace(workspace_prefix) as ws:
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


def run_check_and_simulate_omc(
    model_text: str, model_name: str, workspace_prefix: str = "gf_sim_"
) -> tuple[bool, bool, str]:
    """Full check + simulate. Used for final PASS confirmation on the selected candidate."""
    with temporary_workspace(workspace_prefix) as ws:
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


def choose_candidate(
    ranked: list[Any],
    simulate_attempts: list[dict],
) -> tuple[int | None, float | None, str | None, bool, bool]:
    """Select the best candidate from ranked list and simulate attempts.

    Returns (chosen_id, chosen_temp, chosen_text, chosen_check_pass, chosen_simulate_pass).
    """
    chosen_id: int | None = None
    chosen_temp: float | None = None
    chosen_text: str | None = None
    chosen_check_pass = False
    chosen_simulate_pass = False

    for s in simulate_attempts:
        if s.get("simulate_pass"):
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

    return chosen_id, chosen_temp, chosen_text, chosen_check_pass, chosen_simulate_pass


def compute_summary_core(mode: str, results: list[dict]) -> dict:
    """Compute common aggregate metrics for experiment arms."""
    valid = [r for r in results if not r.get("error")]
    passes = sum(1 for r in valid if r.get("final_status") == "pass")
    total_rounds = 0
    total_any_check = 0
    total_any_sim = 0
    total_candidates = 0
    total_check_pass_candidates = 0
    total_sim_pass_candidates = 0

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
    }
