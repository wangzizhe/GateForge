from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .agent_modelica_v0_13_1_common import (
    CURRENT_MAIN_EXECUTION_CHAIN,
    DEFAULT_BUILDINGS_FIXTURE_HARDPACK_PATH,
    DEFAULT_CAPABILITY_INTERVENTION_EXECUTION_PACK_OUT_DIR,
    DEFAULT_DOCKER_IMAGE,
    DEFAULT_OPENIPSL_FIXTURE_HARDPACK_PATH,
    DEFAULT_POST_INTERVENTION_RUN_OUT_DIR,
    DEFAULT_PRE_INTERVENTION_RUN_OUT_DIR,
    DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH,
    EXPECTED_ADMITTED_INTERVENTION_IDS,
    INTERVENTION_EFFECT_INVALID,
    INTERVENTION_TOGGLE_OFF,
    INTERVENTION_TOGGLE_ON,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _derive_workflow_goal(row: dict) -> str:
    template = str(row.get("workflow_task_template_id") or "")
    if template == "restore_controller_assertion_behavior":
        return "Recover the controller workflow so the validation chain regains the intended assertion behavior."
    if template == "restore_controller_reset_chain":
        return "Recover the controller reset workflow so the reset path regains the intended behavior."
    if template == "restore_conversion_compatibility":
        return "Recover the conversion compatibility workflow so the governed validation chain continues cleanly."
    if template == "restore_multibody_constraint_behavior":
        return "Recover the multibody constraint workflow so the governed validation chain compiles and simulates cleanly."
    if template == "restore_media_record_consistency":
        return "Recover the media record workflow so the carried product-boundary run remains goal aligned."
    if template == "restore_fluid_package_compatibility":
        return "Recover the fluid package compatibility workflow so the product-boundary path remains executable."
    return f"Recover the {str(row.get('family_id') or 'workflow')} path so the governed product-boundary run can continue."


def _docker_ready(*, expected_image: str) -> bool:
    try:
        proc = subprocess.run(
            ["docker", "ps", "--format", "{{.Image}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except Exception:
        return False
    if proc.returncode != 0:
        return False
    return True


def _load_fixture_cases(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = [row for row in list(payload.get("cases") or []) if isinstance(row, dict)]
    small_cases = [row for row in cases if str(row.get("target_scale") or "") == "small"]
    return small_cases if small_cases else cases


def _build_runtime_taskset(
    *,
    v112_product_gap_substrate_builder_path: str,
    buildings_fixture_hardpack_path: str,
    openipsl_fixture_hardpack_path: str,
) -> list[dict]:
    if not Path(v112_product_gap_substrate_builder_path).exists():
        return []
    builder = load_json(v112_product_gap_substrate_builder_path)
    substrate_rows = list(builder.get("product_gap_candidate_table") or [])
    building_cases = _load_fixture_cases(Path(buildings_fixture_hardpack_path))
    openipsl_cases = _load_fixture_cases(Path(openipsl_fixture_hardpack_path))
    fixture_cases = building_cases[:6] + openipsl_cases[:6]
    if len(substrate_rows) != 12 or len(fixture_cases) != 12:
        return []

    runtime_rows = []
    for carried_row, fixture_case in zip(substrate_rows, fixture_cases):
        runtime_rows.append(
            {
                "task_id": str(carried_row.get("task_id") or ""),
                "source_id": str(carried_row.get("source_id") or ""),
                "family_id": str(carried_row.get("family_id") or ""),
                "workflow_task_template_id": str(carried_row.get("workflow_task_template_id") or ""),
                "workflow_goal": _derive_workflow_goal(carried_row),
                "failure_type": str(fixture_case.get("expected_failure_type") or ""),
                "expected_stage": str(fixture_case.get("expected_stage") or ""),
                "source_model_path": str(fixture_case.get("source_model_path") or ""),
                "mutated_model_path": str(fixture_case.get("mutated_model_path") or ""),
                "source_library_path": str(fixture_case.get("source_library_path") or ""),
                "source_package_name": str(fixture_case.get("source_package_name") or ""),
                "source_library_model_path": str(fixture_case.get("source_library_model_path") or ""),
                "source_qualified_model_name": str(fixture_case.get("source_qualified_model_name") or ""),
                "fixture_mutation_id": str(fixture_case.get("mutation_id") or ""),
            }
        )
    return runtime_rows


def _infer_case_outcome(payload: dict) -> str:
    if str(payload.get("executor_status") or "").upper() == "PASS":
        return "goal_level_resolved"
    if bool(payload.get("check_model_pass")) and bool(payload.get("simulate_pass")):
        return "surface_fix_only"
    return "unresolved"


def _run_one_case(*, row: dict, intervention_toggle: str, docker_image: str, out_path: Path) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "gateforge.agent_modelica_live_executor_v1",
        "--task-id",
        str(row.get("task_id") or ""),
        "--failure-type",
        str(row.get("failure_type") or ""),
        "--expected-stage",
        str(row.get("expected_stage") or ""),
        "--workflow-goal",
        str(row.get("workflow_goal") or ""),
        "--source-model-path",
        str(row.get("source_model_path") or ""),
        "--mutated-model-path",
        str(row.get("mutated_model_path") or ""),
        "--source-library-path",
        str(row.get("source_library_path") or ""),
        "--source-package-name",
        str(row.get("source_package_name") or ""),
        "--source-library-model-path",
        str(row.get("source_library_model_path") or ""),
        "--source-qualified-model-name",
        str(row.get("source_qualified_model_name") or ""),
        "--backend",
        "openmodelica_docker",
        "--docker-image",
        docker_image,
        "--planner-backend",
        "rule",
        "--max-rounds",
        "1",
        "--timeout-sec",
        "45",
        "--capability-intervention-pack-enabled",
        intervention_toggle,
        "--out",
        str(out_path),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
        check=False,
        timeout=150,
    )
    if proc.returncode != 0 or not out_path.exists():
        return {
            "task_id": str(row.get("task_id") or ""),
            "execution_source": CURRENT_MAIN_EXECUTION_CHAIN,
            "capability_intervention_pack_enabled": intervention_toggle == INTERVENTION_TOGGLE_ON,
            "executor_status": "FAILED",
            "check_model_pass": False,
            "simulate_pass": False,
            "product_gap_sidecar": {},
            "runtime_error": f"subprocess_exit_{proc.returncode}",
        }
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _build_run_summary(
    *, runtime_rows: list[dict], intervention_toggle: str, out_dir: Path, docker_image: str
) -> dict:
    case_results = []
    out_dir.mkdir(parents=True, exist_ok=True)
    if not runtime_rows:
        return {
            "run_status": "invalid",
            "execution_source": CURRENT_MAIN_EXECUTION_CHAIN,
            "capability_intervention_pack_enabled": intervention_toggle == INTERVENTION_TOGGLE_ON,
            "run_reference": None,
            "case_result_table": [],
            "workflow_resolution_count": 0,
            "goal_alignment_count": 0,
            "surface_fix_only_count": 0,
            "unresolved_count": 0,
            "token_count_total": 0,
            "runtime_error": "runtime_taskset_unavailable",
        }
    if not _docker_ready(expected_image=docker_image):
        return {
            "run_status": "invalid",
            "execution_source": CURRENT_MAIN_EXECUTION_CHAIN,
            "capability_intervention_pack_enabled": intervention_toggle == INTERVENTION_TOGGLE_ON,
            "run_reference": None,
            "case_result_table": [],
            "workflow_resolution_count": 0,
            "goal_alignment_count": 0,
            "surface_fix_only_count": 0,
            "unresolved_count": 0,
            "token_count_total": 0,
            "runtime_error": "docker_not_ready",
        }

    for row in runtime_rows:
        case_out_path = out_dir / "cases" / f"{row['task_id']}.json"
        case_out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = _run_one_case(
            row=row, intervention_toggle=intervention_toggle, docker_image=docker_image, out_path=case_out_path
        )
        sidecar = payload.get("product_gap_sidecar") if isinstance(payload.get("product_gap_sidecar"), dict) else {}
        outcome = _infer_case_outcome(payload)
        case_results.append(
            {
                "task_id": str(row.get("task_id") or ""),
                "source_id": str(row.get("source_id") or ""),
                "family_id": str(row.get("family_id") or ""),
                "fixture_mutation_id": str(row.get("fixture_mutation_id") or ""),
                "execution_source": str(payload.get("execution_source") or CURRENT_MAIN_EXECUTION_CHAIN),
                "capability_intervention_pack_enabled": bool(payload.get("capability_intervention_pack_enabled")),
                "executor_status": str(payload.get("executor_status") or "FAILED"),
                "product_gap_outcome": outcome,
                "goal_alignment": outcome in {"goal_level_resolved", "surface_fix_only"},
                "surface_fix_only": outcome == "surface_fix_only",
                "token_count": int(sidecar.get("token_count") or 0),
                "workflow_goal_reanchoring_observed": bool(sidecar.get("workflow_goal_reanchoring_observed")),
                "execution_strategy_upgrade_applied": bool(sidecar.get("execution_strategy_upgrade_applied")),
                "replan_search_control_upgrade_applied": bool(sidecar.get("replan_search_control_upgrade_applied")),
                "failure_diagnosis_upgrade_applied": bool(sidecar.get("failure_diagnosis_upgrade_applied")),
            }
        )

    workflow_resolution_count = sum(1 for row in case_results if row["product_gap_outcome"] == "goal_level_resolved")
    goal_alignment_count = sum(1 for row in case_results if row["goal_alignment"])
    surface_fix_only_count = sum(1 for row in case_results if row["surface_fix_only"])
    unresolved_count = sum(1 for row in case_results if row["product_gap_outcome"] == "unresolved")
    token_count_total = sum(int(row.get("token_count") or 0) for row in case_results)
    run_payload = {
        "run_status": "ready",
        "execution_source": CURRENT_MAIN_EXECUTION_CHAIN,
        "capability_intervention_pack_enabled": intervention_toggle == INTERVENTION_TOGGLE_ON,
        "run_reference": str(out_dir / "summary.json"),
        "case_result_table": case_results,
        "workflow_resolution_count": workflow_resolution_count,
        "goal_alignment_count": goal_alignment_count,
        "surface_fix_only_count": surface_fix_only_count,
        "unresolved_count": unresolved_count,
        "token_count_total": token_count_total,
    }
    write_json(out_dir / "summary.json", run_payload)
    return run_payload


def _build_side_evidence_status(
    *, pre_rows: list[dict], post_rows: list[dict], token_count_delta: int
) -> tuple[str, list[str], bool]:
    pre_by_task = {str(row.get("task_id") or ""): row for row in pre_rows}
    post_by_task = {str(row.get("task_id") or ""): row for row in post_rows}
    measurable: list[str] = []
    ambiguous = False
    for task_id in sorted(set(pre_by_task) & set(post_by_task)):
        pre = pre_by_task[task_id]
        post = post_by_task[task_id]
        if not bool(pre.get("workflow_goal_reanchoring_observed")) and bool(
            post.get("workflow_goal_reanchoring_observed")
        ):
            measurable.append("workflow_goal_reanchoring_observed")
        elif bool(pre.get("workflow_goal_reanchoring_observed")) and not bool(
            post.get("workflow_goal_reanchoring_observed")
        ):
            ambiguous = True
        for field in (
            "execution_strategy_upgrade_applied",
            "replan_search_control_upgrade_applied",
            "failure_diagnosis_upgrade_applied",
        ):
            if not bool(pre.get(field)) and bool(post.get(field)):
                measurable.append(field)
    if token_count_delta != 0:
        measurable.append("token_count_delta")
    if ambiguous:
        return "ambiguous_or_noise_level_movement", sorted(set(measurable)), True
    if measurable:
        return "measurable_runtime_side_evidence_movement", sorted(set(measurable)), False
    return "no_measurable_runtime_side_evidence_movement", [], False


def _build_comparison_record(*, pre_run: dict, post_run: dict) -> dict:
    pre_ref = pre_run.get("run_reference")
    post_ref = post_run.get("run_reference")
    pre_rows = list(pre_run.get("case_result_table") or [])
    post_rows = list(post_run.get("case_result_table") or [])
    same_execution_source = (
        str(pre_run.get("execution_source") or "") == CURRENT_MAIN_EXECUTION_CHAIN
        and str(post_run.get("execution_source") or "") == CURRENT_MAIN_EXECUTION_CHAIN
    )
    same_case_requirement_met = sorted(
        str(row.get("task_id") or "") for row in pre_rows
    ) == sorted(str(row.get("task_id") or "") for row in post_rows)
    token_count_delta = int(post_run.get("token_count_total") or 0) - int(pre_run.get("token_count_total") or 0)
    sidecar_status, measurable_side_fields, ambiguous_side_movement = _build_side_evidence_status(
        pre_rows=pre_rows,
        post_rows=post_rows,
        token_count_delta=token_count_delta,
    )
    return {
        "pre_intervention_run_reference": pre_ref,
        "post_intervention_run_reference": post_ref,
        "comparison_mode": "pre_vs_post_on_same_cases",
        "same_execution_source": same_execution_source,
        "same_case_requirement_met": same_case_requirement_met,
        "runtime_measurement_source": CURRENT_MAIN_EXECUTION_CHAIN,
        "pre_intervention_workflow_resolution_count": int(pre_run.get("workflow_resolution_count") or 0),
        "pre_intervention_goal_alignment_count": int(pre_run.get("goal_alignment_count") or 0),
        "pre_intervention_surface_fix_only_count": int(pre_run.get("surface_fix_only_count") or 0),
        "pre_intervention_unresolved_count": int(pre_run.get("unresolved_count") or 0),
        "post_intervention_workflow_resolution_count": int(post_run.get("workflow_resolution_count") or 0),
        "post_intervention_goal_alignment_count": int(post_run.get("goal_alignment_count") or 0),
        "post_intervention_surface_fix_only_count": int(post_run.get("surface_fix_only_count") or 0),
        "post_intervention_unresolved_count": int(post_run.get("unresolved_count") or 0),
        "workflow_resolution_delta": int(post_run.get("workflow_resolution_count") or 0)
        - int(pre_run.get("workflow_resolution_count") or 0),
        "goal_alignment_delta": int(post_run.get("goal_alignment_count") or 0)
        - int(pre_run.get("goal_alignment_count") or 0),
        "surface_fix_only_delta": int(post_run.get("surface_fix_only_count") or 0)
        - int(pre_run.get("surface_fix_only_count") or 0),
        "unresolved_delta": int(post_run.get("unresolved_count") or 0)
        - int(pre_run.get("unresolved_count") or 0),
        "token_count_delta": token_count_delta,
        "product_gap_sidecar_comparison_status": sidecar_status,
        "measurable_side_evidence_fields": measurable_side_fields,
        "ambiguous_side_evidence_movement": ambiguous_side_movement,
    }


def build_v131_capability_intervention_execution_pack(
    *,
    v112_product_gap_substrate_builder_path: str = str(DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH),
    buildings_fixture_hardpack_path: str = str(DEFAULT_BUILDINGS_FIXTURE_HARDPACK_PATH),
    openipsl_fixture_hardpack_path: str = str(DEFAULT_OPENIPSL_FIXTURE_HARDPACK_PATH),
    pre_intervention_run_path: str = "",
    post_intervention_run_path: str = "",
    pre_run_out_dir: str = str(DEFAULT_PRE_INTERVENTION_RUN_OUT_DIR),
    post_run_out_dir: str = str(DEFAULT_POST_INTERVENTION_RUN_OUT_DIR),
    out_dir: str = str(DEFAULT_CAPABILITY_INTERVENTION_EXECUTION_PACK_OUT_DIR),
    docker_image: str = DEFAULT_DOCKER_IMAGE,
) -> dict:
    out_root = Path(out_dir)
    if pre_intervention_run_path and Path(pre_intervention_run_path).exists():
        pre_run = load_json(pre_intervention_run_path)
    else:
        runtime_rows = _build_runtime_taskset(
            v112_product_gap_substrate_builder_path=v112_product_gap_substrate_builder_path,
            buildings_fixture_hardpack_path=buildings_fixture_hardpack_path,
            openipsl_fixture_hardpack_path=openipsl_fixture_hardpack_path,
        )
        pre_run = _build_run_summary(
            runtime_rows=runtime_rows,
            intervention_toggle=INTERVENTION_TOGGLE_OFF,
            out_dir=Path(pre_run_out_dir),
            docker_image=docker_image,
        )

    if post_intervention_run_path and Path(post_intervention_run_path).exists():
        post_run = load_json(post_intervention_run_path)
    else:
        runtime_rows = _build_runtime_taskset(
            v112_product_gap_substrate_builder_path=v112_product_gap_substrate_builder_path,
            buildings_fixture_hardpack_path=buildings_fixture_hardpack_path,
            openipsl_fixture_hardpack_path=openipsl_fixture_hardpack_path,
        )
        post_run = _build_run_summary(
            runtime_rows=runtime_rows,
            intervention_toggle=INTERVENTION_TOGGLE_ON,
            out_dir=Path(post_run_out_dir),
            docker_image=docker_image,
        )

    comparison = _build_comparison_record(pre_run=pre_run, post_run=post_run)
    post_rows = list(post_run.get("case_result_table") or [])
    pack_enabled_in_post = bool(post_run.get("capability_intervention_pack_enabled"))
    capability_intervention_execution_pack = {
        "intervention_rows": [
            {
                "intervention_id": "bounded_execution_strategy_upgrade_v1",
                "intervention_family": "capability_level_execution_strategy_improvement",
                "intervention_execution_shape": "composite_capability_patch",
                "bounded_change_surface": "L2_structured_plan_and_execution_strategy_upgrade",
                "intervention_enabled": bool(
                    pack_enabled_in_post
                    and any(bool(row.get("execution_strategy_upgrade_applied")) for row in post_rows)
                ),
                "carried_baseline_reference": "v0_13_0_governance_pack.admitted_intervention_set",
            },
            {
                "intervention_id": "bounded_replan_search_control_upgrade_v1",
                "intervention_family": "search_control_and_replan_improvement",
                "intervention_execution_shape": "composite_capability_patch",
                "bounded_change_surface": "L2_replan_policy_and_search_budget_control_upgrade",
                "intervention_enabled": bool(
                    pack_enabled_in_post
                    and any(bool(row.get("replan_search_control_upgrade_applied")) for row in post_rows)
                ),
                "carried_baseline_reference": "v0_13_0_governance_pack.admitted_intervention_set",
            },
            {
                "intervention_id": "bounded_failure_diagnosis_upgrade_v1",
                "intervention_family": "failure_state_diagnosis_improvement",
                "intervention_execution_shape": "composite_capability_patch",
                "bounded_change_surface": "L3_L4_failure_bucket_and_diagnosis_chain_upgrade",
                "intervention_enabled": bool(
                    pack_enabled_in_post
                    and any(bool(row.get("failure_diagnosis_upgrade_applied")) for row in post_rows)
                ),
                "carried_baseline_reference": "v0_13_0_governance_pack.admitted_intervention_set",
            },
        ],
    }
    all_interventions_enabled = all(
        bool(row.get("intervention_enabled"))
        for row in list(capability_intervention_execution_pack.get("intervention_rows") or [])
    )
    status = "ready"
    if (
        not comparison.get("pre_intervention_run_reference")
        or not comparison.get("post_intervention_run_reference")
        or not bool(comparison.get("same_execution_source"))
        or not bool(comparison.get("same_case_requirement_met"))
        or not all_interventions_enabled
    ):
        status = "invalid"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_capability_intervention_execution_pack",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status == "ready" else "FAIL",
        "capability_intervention_execution_pack_status": status,
        "pre_intervention_live_run": pre_run,
        "post_intervention_live_run": post_run,
        "pre_post_capability_comparison_record": comparison,
        "capability_intervention_execution_pack": capability_intervention_execution_pack,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.13.1 Capability Intervention Execution Pack",
                "",
                f"- capability_intervention_execution_pack_status: `{status}`",
                f"- pre_intervention_run_reference: `{comparison.get('pre_intervention_run_reference')}`",
                f"- post_intervention_run_reference: `{comparison.get('post_intervention_run_reference')}`",
                f"- same_execution_source: `{comparison.get('same_execution_source')}`",
                f"- all_interventions_enabled: `{all_interventions_enabled}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.13.1 capability intervention execution pack.")
    parser.add_argument("--v112-product-gap-substrate-builder", default=str(DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--buildings-fixture-hardpack", default=str(DEFAULT_BUILDINGS_FIXTURE_HARDPACK_PATH))
    parser.add_argument("--openipsl-fixture-hardpack", default=str(DEFAULT_OPENIPSL_FIXTURE_HARDPACK_PATH))
    parser.add_argument("--pre-intervention-run", default="")
    parser.add_argument("--post-intervention-run", default="")
    parser.add_argument("--pre-run-out-dir", default=str(DEFAULT_PRE_INTERVENTION_RUN_OUT_DIR))
    parser.add_argument("--post-run-out-dir", default=str(DEFAULT_POST_INTERVENTION_RUN_OUT_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_CAPABILITY_INTERVENTION_EXECUTION_PACK_OUT_DIR))
    parser.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    args = parser.parse_args()
    payload = build_v131_capability_intervention_execution_pack(
        v112_product_gap_substrate_builder_path=str(args.v112_product_gap_substrate_builder),
        buildings_fixture_hardpack_path=str(args.buildings_fixture_hardpack),
        openipsl_fixture_hardpack_path=str(args.openipsl_fixture_hardpack),
        pre_intervention_run_path=str(args.pre_intervention_run),
        post_intervention_run_path=str(args.post_intervention_run),
        pre_run_out_dir=str(args.pre_run_out_dir),
        post_run_out_dir=str(args.post_run_out_dir),
        out_dir=str(args.out_dir),
        docker_image=str(args.docker_image),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "capability_intervention_execution_pack_status": payload.get(
                    "capability_intervention_execution_pack_status"
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
