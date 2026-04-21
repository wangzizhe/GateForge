"""Two-turn context experiment for phantom and compound structural families (v0.19.42)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN", "80")
os.environ.setdefault("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", "180")

from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text
from gateforge.agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)
from scripts.diagnostic_context_dm_v0_19_35 import build_dm_diagnostic_context

V36_RESULTS = REPO_ROOT / "artifacts" / "dm_context_experiment_v0_19_36" / "experiment_results.jsonl"
V36_PATCHED = REPO_ROOT / "artifacts" / "dm_context_experiment_v0_19_36" / "patched_models"
V39_RESULTS = REPO_ROOT / "artifacts" / "compound_dm_context_experiment_v0_19_39" / "experiment_results.jsonl"
V39_PATCHED = REPO_ROOT / "artifacts" / "compound_dm_context_experiment_v0_19_39" / "patched_models"
ADMITTED_V34 = REPO_ROOT / "artifacts" / "structural_mutation_experiment_v0_19_34" / "admitted_cases.jsonl"
ADMITTED_V38 = REPO_ROOT / "artifacts" / "compound_underdetermined_experiment_v0_19_38" / "admitted_cases.jsonl"
OUT_DIR = REPO_ROOT / "artifacts" / "multiturn_context_experiment_v0_19_42"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
PLANNER_BACKEND = "gemini"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _run_check(model_text: str, model_name: str) -> tuple[bool, str]:
    with temporary_workspace("gf_exp42mt_") as ws:
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
        _, output, check_ok, _ = run_check_and_simulate(
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


def _classify_llm_error(err: str) -> str:
    if not err:
        return ""
    e = err.lower()
    if any(x in e for x in ("503", "502", "service_unavailable", "rate_limited", "timeout", "url_error", "budget_exceeded")):
        return "service_error"
    if any(x in e for x in ("missing_patched_model_text", "no_output", "json")):
        return "format_err"
    return "llm_fail"


def _run_llm_turn(*, model_text: str, model_name: str, failure_type: str, workflow_goal: str, error_excerpt: str, current_round: int) -> tuple[dict, str | None]:
    patched, err, _ = llm_repair_model_text(
        planner_backend=PLANNER_BACKEND,
        original_text=model_text,
        failure_type=failure_type,
        expected_stage="check",
        error_excerpt=error_excerpt,
        repair_actions=["Restore the missing defining equations or declarations and remove any leftover phantom-variable artifacts."],
        model_name=model_name,
        workflow_goal=workflow_goal,
        current_round=current_round,
    )
    if err or patched is None:
        err_str = err or "no_output"
        return {
            "fix_pass": False,
            "llm_error": err_str,
            "error_class": _classify_llm_error(err_str),
            "omc_output_snippet": "",
        }, None
    check_pass, omc_out = _run_check(patched, model_name)
    return {
        "fix_pass": check_pass,
        "llm_error": "",
        "error_class": "",
        "omc_output_snippet": omc_out[:500],
    }, patched


def _load_case_maps() -> tuple[dict[str, dict], dict[str, dict]]:
    admitted34 = {row["candidate_id"]: row for row in _read_jsonl(ADMITTED_V34)}
    admitted38 = {row["candidate_id"]: row for row in _read_jsonl(ADMITTED_V38)}
    return admitted34, admitted38


def run_experiment() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    patched_dir = OUT_DIR / "patched_models"
    patched_dir.mkdir(exist_ok=True)
    admitted34, admitted38 = _load_case_maps()

    results = []

    # Phantom: compare v0.19.36 C single-turn with DM-guided turn 2
    for row in _read_jsonl(V36_RESULTS):
        cid = row["candidate_id"]
        case = admitted34.get(cid)
        if not case:
            continue
        patched_t1 = V36_PATCHED / f"{cid}_C.mo"
        if row["condition_c"]["fix_pass"] or not patched_t1.exists():
            continue
        patched_t1_text = patched_t1.read_text(encoding="utf-8")
        dm_turn2 = build_dm_diagnostic_context(patched_t1_text)
        result_t2, patched_t2 = _run_llm_turn(
            model_text=patched_t1_text,
            model_name=case["model_name"],
            failure_type=case["failure_type"],
            workflow_goal=case["workflow_goal"],
            error_excerpt=dm_turn2[:2000],
            current_round=2,
        )
        if patched_t2 is not None:
            (patched_dir / f"{cid}_phantom_C_T2.mo").write_text(patched_t2, encoding="utf-8")
        results.append({
            "candidate_id": cid,
            "family": "phantom_variable",
            "mode": "C_dm_multiturn",
            "turn1_pass": row["condition_c"]["fix_pass"],
            "turn2_attempted": True,
            "turn2_pass": result_t2["fix_pass"],
            "cumulative_pass": result_t2["fix_pass"],
            "turn2_error_class": result_t2.get("error_class", ""),
        })

    # Compound: compare A raw and C per-variable over 2 turns
    for row in _read_jsonl(V39_RESULTS):
        cid = row["candidate_id"]
        case = admitted38.get(cid)
        if not case:
            continue
        for suffix, condition_key, mode in (("A", "condition_a", "A_raw_multiturn"), ("C", "condition_c", "C_pervar_multiturn")):
            result_t1 = row[condition_key]
            patched_t1 = V39_PATCHED / f"{cid}_{suffix}.mo"
            if result_t1["fix_pass"] or not patched_t1.exists():
                continue
            patched_t1_text = patched_t1.read_text(encoding="utf-8")
            if suffix == "A":
                _, turn2_excerpt = _run_check(patched_t1_text, case["model_name"])
            else:
                turn2_excerpt = build_dm_diagnostic_context(patched_t1_text)
            result_t2, patched_t2 = _run_llm_turn(
                model_text=patched_t1_text,
                model_name=case["model_name"],
                failure_type=case["failure_type"],
                workflow_goal=case["workflow_goal"],
                error_excerpt=turn2_excerpt[:2000],
                current_round=2,
            )
            if patched_t2 is not None:
                (patched_dir / f"{cid}_{mode}_T2.mo").write_text(patched_t2, encoding="utf-8")
            results.append({
                "candidate_id": cid,
                "family": "compound_underdetermined",
                "mode": mode,
                "turn1_pass": result_t1["fix_pass"],
                "turn2_attempted": True,
                "turn2_pass": result_t2["fix_pass"],
                "cumulative_pass": result_t2["fix_pass"],
                "turn2_error_class": result_t2.get("error_class", ""),
            })

    (OUT_DIR / "experiment_results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + ("\n" if results else ""),
        encoding="utf-8",
    )
    summary = {"version": "v0.19.42", "by_mode": {}}
    for mode in sorted({r["mode"] for r in results}):
        rows = [r for r in results if r["mode"] == mode]
        summary["by_mode"][mode] = {
            "n_cases": len(rows),
            "turn2_pass_n": sum(1 for r in rows if r["turn2_pass"]),
            "cumulative_pass_rate": round(sum(1 for r in rows if r["cumulative_pass"]) / len(rows), 3) if rows else 0.0,
        }
    (OUT_DIR / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run_experiment()
