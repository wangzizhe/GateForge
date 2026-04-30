from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from .agent_modelica_benchmark_loader_v0_29_0 import load_and_validate_task
from .agent_modelica_tool_use_harness_v0_28_0 import _run_omc

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASK_ROOT = REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "tasks" / "repair"
DEFAULT_REFERENCE_ROOT = REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "reference_repairs" / "v0_35_8"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hidden_solvability_audit_v0_35_8"

V0358_CASE_IDS = (
    "sem_22_arrayed_three_branch_probe_bus",
    "sem_23_nested_probe_contract_bus",
    "sem_24_bridge_probe_transfer_bus",
)

OmcRunner = Callable[[str, str, float, int], tuple[int, str, bool, bool]]


def _extract_model_name(model_text: str) -> str:
    match = re.search(r"^\s*model\s+([A-Za-z_][A-Za-z0-9_]*)", model_text, re.MULTILINE)
    return match.group(1) if match else ""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _default_omc_runner(model_text: str, model_name: str, stop_time: float, intervals: int) -> tuple[int, str, bool, bool]:
    return _run_omc(model_text, model_name, stop_time=stop_time, intervals=intervals)


def _audit_case(
    *,
    case_id: str,
    task_root: Path,
    reference_root: Path,
    omc_runner: OmcRunner,
) -> dict[str, Any]:
    task_path = task_root / f"{case_id}.json"
    task, errors = load_and_validate_task(task_path)
    reference_path = reference_root / f"{case_id}.json"
    reference = _load_json(reference_path)
    if task is None or errors:
        return {
            "case_id": case_id,
            "status": "REVIEW",
            "validation_errors": errors or ["task_missing_or_invalid"],
            "reference_present": bool(reference),
        }
    reference_text = str(reference.get("reference_model_text") or "")
    initial_model_text = str(task.get("initial_model") or "")
    initial_model_name = _extract_model_name(initial_model_text)
    reference_model_name = _extract_model_name(reference_text)
    verification = task.get("verification") if isinstance(task.get("verification"), dict) else {}
    simulate = verification.get("simulate") if isinstance(verification.get("simulate"), dict) else {}
    stop_time = float(simulate.get("stop_time") or 0.05)
    intervals = int(simulate.get("intervals") or 5)
    blockers: list[str] = []
    if not reference_text.strip():
        blockers.append("reference_model_missing")
    if initial_model_name != reference_model_name:
        blockers.append("model_name_changed")
    if reference_text.strip() and initial_model_text.strip() and reference_text == initial_model_text:
        blockers.append("reference_identical_to_initial_model")
    if blockers:
        return {
            "case_id": case_id,
            "status": "REVIEW",
            "reference_present": bool(reference_text.strip()),
            "initial_model_name": initial_model_name,
            "reference_model_name": reference_model_name,
            "blockers": blockers,
        }
    _, omc_output, check_pass, simulate_pass = omc_runner(reference_text, reference_model_name, stop_time, intervals)
    status = "PASS" if check_pass and simulate_pass else "REVIEW"
    return {
        "case_id": case_id,
        "status": status,
        "reference_present": True,
        "initial_model_name": initial_model_name,
        "reference_model_name": reference_model_name,
        "check_model_pass": check_pass,
        "simulate_pass": simulate_pass,
        "reference_hidden_from_prompt": True,
        "reference_used_for_wrapper_repair": False,
        "omc_output_snippet": str(omc_output or "")[:1200],
        "blockers": [] if status == "PASS" else ["reference_did_not_pass_omc"],
    }


def build_hidden_solvability_audit(
    *,
    task_root: Path = DEFAULT_TASK_ROOT,
    reference_root: Path = DEFAULT_REFERENCE_ROOT,
    out_dir: Path = DEFAULT_OUT_DIR,
    case_ids: tuple[str, ...] = V0358_CASE_IDS,
    omc_runner: OmcRunner = _default_omc_runner,
) -> dict[str, Any]:
    rows = [
        _audit_case(case_id=case_id, task_root=task_root, reference_root=reference_root, omc_runner=omc_runner)
        for case_id in case_ids
    ]
    pass_count = sum(1 for row in rows if row.get("status") == "PASS")
    missing_reference_count = sum(1 for row in rows if not row.get("reference_present"))
    summary = {
        "version": "v0.35.8",
        "status": "PASS" if pass_count == len(case_ids) else "REVIEW",
        "analysis_scope": "hidden_solvability_audit",
        "case_count": len(case_ids),
        "pass_count": pass_count,
        "missing_reference_count": missing_reference_count,
        "case_ids": list(case_ids),
        "rows": rows,
        "decision": (
            "connector_flow_family_hidden_references_pass_omc"
            if pass_count == len(case_ids)
            else "connector_flow_family_hidden_references_need_review"
        ),
        "discipline": {
            "reference_injected_into_prompt": False,
            "deterministic_repair_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "wrapper_patch_generated": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
