from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl
from .agent_modelica_omc_workspace_v1 import run_check_and_simulate, temporary_workspace


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VARIANTS = REPO_ROOT / "artifacts" / "hard_core_adjacent_variants_v0_48_1" / "tasks.jsonl"
DEFAULT_GATE = REPO_ROOT / "artifacts" / "hard_core_adjacent_gate_v0_48_2" / "passed_case_ids.txt"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_core_adjacent_admission_v0_48_3"

DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

CheckFn = Callable[[dict[str, Any]], tuple[bool, bool, str]]


def _load_passed_case_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def infer_model_name(model_text: str) -> str:
    match = re.search(r"\bmodel\s+([A-Za-z_][A-Za-z0-9_]*)", model_text)
    return match.group(1) if match else ""


def classify_admission(check_ok: bool, simulate_ok: bool, output: str) -> str:
    lowered = output.lower()
    if "permission denied" in lowered and "docker" in lowered:
        return "environment_blocked_docker_permission"
    if "cannot connect to the docker" in lowered or "docker daemon" in lowered:
        return "environment_blocked_docker_unavailable"
    if check_ok and simulate_ok:
        return "not_admitted_already_passes"
    if check_ok and not simulate_ok:
        return "admitted_simulation_or_build_failure"
    if "too few equations" in lowered or "under-determined" in lowered:
        return "admitted_under_determined"
    if "too many equations" in lowered or "over-determined" in lowered:
        return "admitted_over_determined"
    if "error:" in lowered or "failed" in lowered:
        return "admitted_model_check_or_translation_failure"
    return "review_no_clear_failure_signal"


def run_omc_admission_check(task: dict[str, Any]) -> tuple[bool, bool, str]:
    model_text = str(task.get("initial_model") or "")
    model_name = infer_model_name(model_text)
    verification = task.get("verification") if isinstance(task.get("verification"), dict) else {}
    simulate = verification.get("simulate") if isinstance(verification.get("simulate"), dict) else {}
    stop_time = float(simulate.get("stop_time") or 0.1)
    intervals = int(simulate.get("intervals") or 100)
    with temporary_workspace(prefix="gf_v048_admission_") as raw_workspace:
        workspace = Path(raw_workspace)
        model_path = workspace / "model.mo"
        model_path.write_text(model_text, encoding="utf-8")
        _, output, check_ok, simulate_ok = run_check_and_simulate(
            workspace=workspace,
            model_load_files=["model.mo"],
            model_name=model_name,
            timeout_sec=60,
            backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
            stop_time=stop_time,
            intervals=intervals,
        )
    return check_ok, simulate_ok, output


def build_hard_core_adjacent_admission(
    *,
    variants: list[dict[str, Any]],
    passed_case_ids: set[str],
    check_fn: CheckFn,
    version: str = "v0.48.3",
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for task in variants:
        case_id = str(task.get("case_id") or "")
        if passed_case_ids and case_id not in passed_case_ids:
            continue
        model_name = infer_model_name(str(task.get("initial_model") or ""))
        if not model_name:
            rows.append(
                {
                    "case_id": case_id,
                    "model_name": "",
                    "check_ok": False,
                    "simulate_ok": False,
                    "admission_status": "review_missing_model_name",
                    "output_excerpt": "",
                }
            )
            continue
        check_ok, simulate_ok, output = check_fn(task)
        rows.append(
            {
                "case_id": case_id,
                "model_name": model_name,
                "check_ok": bool(check_ok),
                "simulate_ok": bool(simulate_ok),
                "admission_status": classify_admission(check_ok, simulate_ok, output),
                "output_excerpt": output[:1200],
            }
        )
    admitted = [row for row in rows if str(row["admission_status"]).startswith("admitted_")]
    environment_blocked = [row for row in rows if str(row["admission_status"]).startswith("environment_blocked_")]
    review = [
        row
        for row in rows
        if not str(row["admission_status"]).startswith("admitted_")
        and not str(row["admission_status"]).startswith("environment_blocked_")
    ]
    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row["admission_status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "version": version,
        "analysis_scope": "hard_core_adjacent_omc_admission",
        "status": "PASS" if rows and len(admitted) >= 8 else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "case_count": len(rows),
        "admitted_case_count": len(admitted),
        "environment_blocked_count": len(environment_blocked),
        "review_case_count": len(review),
        "admitted_case_ids": [row["case_id"] for row in admitted],
        "review_case_ids": [row["case_id"] for row in review],
        "admission_status_counts": dict(sorted(status_counts.items())),
        "results": sorted(rows, key=lambda item: item["case_id"]),
        "next_action": "run_base_tool_use_baseline_for_admitted_cases",
        "scope_note": "Admission proves the task has a real OMC failure signal. It does not prove benchmark hardness or Agent ability.",
    }


def write_hard_core_adjacent_admission_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "admitted_case_ids.txt").write_text(
        "\n".join(summary.get("admitted_case_ids") or []) + "\n",
        encoding="utf-8",
    )


def run_hard_core_adjacent_admission(
    *,
    variants_path: Path = DEFAULT_VARIANTS,
    gate_path: Path = DEFAULT_GATE,
    out_dir: Path = DEFAULT_OUT_DIR,
    check_fn: CheckFn = run_omc_admission_check,
) -> dict[str, Any]:
    summary = build_hard_core_adjacent_admission(
        variants=load_jsonl(variants_path),
        passed_case_ids=_load_passed_case_ids(gate_path),
        check_fn=check_fn,
    )
    write_hard_core_adjacent_admission_outputs(out_dir=out_dir, summary=summary)
    return summary
