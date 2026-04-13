from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .agent_modelica_v0_13_1_capability_intervention_execution_pack import (
    _build_runtime_taskset,
    _docker_ready,
    _infer_case_outcome,
)
from .agent_modelica_v0_14_1_common import (
    BROADER_CHANGE_TOGGLE_OFF,
    BROADER_CHANGE_TOGGLE_ON,
    CURRENT_MAIN_EXECUTION_CHAIN,
    DEFAULT_BROADER_CHANGE_EXECUTION_PACK_OUT_DIR,
    DEFAULT_BUILDINGS_FIXTURE_HARDPACK_PATH,
    DEFAULT_DOCKER_IMAGE,
    DEFAULT_OPENIPSL_FIXTURE_HARDPACK_PATH,
    DEFAULT_POST_BROADER_CHANGE_RUN_OUT_DIR,
    DEFAULT_PRE_BROADER_CHANGE_RUN_OUT_DIR,
    DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH,
    DEFAULT_V140_GOVERNANCE_PACK_PATH,
    EXPECTED_ADMITTED_BROADER_CHANGE_IDS,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _run_one_case(*, row: dict, broader_change_toggle: str, docker_image: str, out_path: Path) -> dict:
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
        "--broader-change-pack-enabled",
        broader_change_toggle,
        "--out",
        str(out_path),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if proc.returncode != 0 or not out_path.exists():
        return {
            "task_id": str(row.get("task_id") or ""),
            "execution_source": CURRENT_MAIN_EXECUTION_CHAIN,
            "broader_change_pack_enabled": broader_change_toggle == BROADER_CHANGE_TOGGLE_ON,
            "executor_status": "FAILED",
            "check_model_pass": False,
            "simulate_pass": False,
            "product_gap_sidecar": {},
            "runtime_error": f"subprocess_exit_{proc.returncode}",
        }
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _build_run_summary(
    *, runtime_rows: list[dict], broader_change_toggle: str, out_dir: Path, docker_image: str
) -> dict:
    case_results = []
    out_dir.mkdir(parents=True, exist_ok=True)
    if not runtime_rows:
        return {
            "run_status": "invalid",
            "execution_source": CURRENT_MAIN_EXECUTION_CHAIN,
            "broader_change_pack_enabled": broader_change_toggle == BROADER_CHANGE_TOGGLE_ON,
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
            "broader_change_pack_enabled": broader_change_toggle == BROADER_CHANGE_TOGGLE_ON,
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
            row=row,
            broader_change_toggle=broader_change_toggle,
            docker_image=docker_image,
            out_path=case_out_path,
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
                "broader_change_pack_enabled": bool(payload.get("broader_change_pack_enabled")),
                "executor_status": str(payload.get("executor_status") or "FAILED"),
                "product_gap_outcome": outcome,
                "goal_alignment": outcome in {"goal_level_resolved", "surface_fix_only"},
                "surface_fix_only": outcome == "surface_fix_only",
                "token_count": int(sidecar.get("token_count") or 0),
                "broader_execution_policy_restructuring_applied": bool(
                    sidecar.get("broader_execution_policy_restructuring_applied")
                ),
                "governed_model_upgrade_applied": bool(sidecar.get("governed_model_upgrade_applied")),
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
        "broader_change_pack_enabled": broader_change_toggle == BROADER_CHANGE_TOGGLE_ON,
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


def _build_side_evidence_status(*, pre_rows: list[dict], post_rows: list[dict], token_count_delta: int) -> tuple[str, list[str], bool]:
    pre_by_task = {str(row.get("task_id") or ""): row for row in pre_rows}
    post_by_task = {str(row.get("task_id") or ""): row for row in post_rows}
    measurable: list[str] = []
    ambiguous = False
    for task_id in sorted(set(pre_by_task) & set(post_by_task)):
        pre = pre_by_task[task_id]
        post = post_by_task[task_id]
        for field in (
            "broader_execution_policy_restructuring_applied",
            "governed_model_upgrade_applied",
        ):
            if not bool(pre.get(field)) and bool(post.get(field)):
                measurable.append(field)
            elif bool(pre.get(field)) and not bool(post.get(field)):
                ambiguous = True
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


def build_v141_broader_change_execution_pack(
    *,
    v140_governance_pack_path: str = str(DEFAULT_V140_GOVERNANCE_PACK_PATH),
    v112_product_gap_substrate_builder_path: str = str(DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH),
    buildings_fixture_hardpack_path: str = str(DEFAULT_BUILDINGS_FIXTURE_HARDPACK_PATH),
    openipsl_fixture_hardpack_path: str = str(DEFAULT_OPENIPSL_FIXTURE_HARDPACK_PATH),
    pre_intervention_run_path: str = "",
    post_intervention_run_path: str = "",
    pre_run_out_dir: str = str(DEFAULT_PRE_BROADER_CHANGE_RUN_OUT_DIR),
    post_run_out_dir: str = str(DEFAULT_POST_BROADER_CHANGE_RUN_OUT_DIR),
    out_dir: str = str(DEFAULT_BROADER_CHANGE_EXECUTION_PACK_OUT_DIR),
    docker_image: str = DEFAULT_DOCKER_IMAGE,
) -> dict:
    out_root = Path(out_dir)
    governance_pack = load_json(v140_governance_pack_path)
    admission = (
        governance_pack.get("broader_change_admission")
        if isinstance(governance_pack.get("broader_change_admission"), dict)
        else {}
    )
    admitted_rows = list(admission.get("admitted_rows") or [])
    admitted_ids = [str(row.get("candidate_id") or "") for row in admitted_rows if isinstance(row, dict)]

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
            broader_change_toggle=BROADER_CHANGE_TOGGLE_OFF,
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
            broader_change_toggle=BROADER_CHANGE_TOGGLE_ON,
            out_dir=Path(post_run_out_dir),
            docker_image=docker_image,
        )

    comparison = _build_comparison_record(pre_run=pre_run, post_run=post_run)
    post_rows = list(post_run.get("case_result_table") or [])
    pack_enabled_in_post = bool(post_run.get("broader_change_pack_enabled"))
    broader_change_pack = {
        "candidate_rows": [
            {
                "candidate_id": "broader_L2_execution_policy_restructuring_v1",
                "candidate_family": "broader_execution_policy_restructuring",
                "broader_change_surface": "L2_execution_policy_restructuring_beyond_bounded_strategy_hints",
                "candidate_enabled": bool(pack_enabled_in_post),
                "runtime_evidence_hook_seen": bool(
                    pack_enabled_in_post
                    and any(bool(row.get("broader_execution_policy_restructuring_applied")) for row in post_rows)
                ),
                "carried_baseline_reference": "v0_14_0_governance_pack.named_first_broader_change_pack_ids",
            },
            {
                "candidate_id": "governed_llm_backbone_upgrade_v1",
                "candidate_family": "governed_model_upgrade_candidate",
                "broader_change_surface": "LLM_backbone_upgrade_under_same_executor_contract",
                "candidate_enabled": bool(pack_enabled_in_post),
                "runtime_evidence_hook_seen": bool(
                    pack_enabled_in_post
                    and any(bool(row.get("governed_model_upgrade_applied")) for row in post_rows)
                ),
                "carried_baseline_reference": "v0_14_0_governance_pack.named_first_broader_change_pack_ids",
            },
        ],
    }
    all_candidates_enabled = all(
        bool(row.get("candidate_enabled")) for row in list(broader_change_pack.get("candidate_rows") or [])
    )
    ids_match_governance = frozenset(admitted_ids) == EXPECTED_ADMITTED_BROADER_CHANGE_IDS

    status = "ready"
    if (
        not comparison.get("pre_intervention_run_reference")
        or not comparison.get("post_intervention_run_reference")
        or not bool(comparison.get("same_execution_source"))
        or not bool(comparison.get("same_case_requirement_met"))
        or not all_candidates_enabled
        or not ids_match_governance
    ):
        status = "invalid"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_broader_change_execution_pack",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status == "ready" else "FAIL",
        "broader_change_execution_pack_status": status,
        "pre_intervention_live_run": pre_run,
        "post_intervention_live_run": post_run,
        "pre_post_broader_change_comparison_record": comparison,
        "broader_change_pack": {
            **broader_change_pack,
            "admitted_candidate_ids": admitted_ids,
            "ids_match_governance": ids_match_governance,
        },
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.14.1 Broader Change Execution Pack",
                "",
                f"- broader_change_execution_pack_status: `{status}`",
                f"- pre_intervention_run_reference: `{comparison.get('pre_intervention_run_reference')}`",
                f"- post_intervention_run_reference: `{comparison.get('post_intervention_run_reference')}`",
                f"- same_execution_source: `{comparison.get('same_execution_source')}`",
                f"- all_candidates_enabled: `{all_candidates_enabled}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.14.1 broader change execution pack.")
    parser.add_argument("--v140-governance-pack", default=str(DEFAULT_V140_GOVERNANCE_PACK_PATH))
    parser.add_argument("--v112-product-gap-substrate-builder", default=str(DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--buildings-fixture-hardpack", default=str(DEFAULT_BUILDINGS_FIXTURE_HARDPACK_PATH))
    parser.add_argument("--openipsl-fixture-hardpack", default=str(DEFAULT_OPENIPSL_FIXTURE_HARDPACK_PATH))
    parser.add_argument("--pre-intervention-run", default="")
    parser.add_argument("--post-intervention-run", default="")
    parser.add_argument("--pre-run-out-dir", default=str(DEFAULT_PRE_BROADER_CHANGE_RUN_OUT_DIR))
    parser.add_argument("--post-run-out-dir", default=str(DEFAULT_POST_BROADER_CHANGE_RUN_OUT_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_BROADER_CHANGE_EXECUTION_PACK_OUT_DIR))
    parser.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    args = parser.parse_args()
    payload = build_v141_broader_change_execution_pack(
        v140_governance_pack_path=str(args.v140_governance_pack),
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
                "broader_change_execution_pack_status": payload.get("broader_change_execution_pack_status"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
