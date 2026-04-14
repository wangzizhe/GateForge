from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json

DEFAULT_CASE_BANK_PATH = REPO_ROOT / "artifacts" / "agent_modelica_repair_playbook_v1" / "corpus.json"
DEFAULT_CASE_BANK_SIZE = 80
DEFAULT_CASE_BANK_PATHS = (
    REPO_ROOT / "artifacts" / "agent_modelica_repair_playbook_v1" / "corpus.json",
    REPO_ROOT / "artifacts" / "agent_modelica_l4_challenge_pack_v0_repro_fixed02" / "taskset_frozen.json",
    REPO_ROOT / "artifacts" / "agent_modelica_v0_3_3_generation_scripted" / "multi_round" / "merged_repair_history.json",
)

_FAILURE_TO_TAXONOMY = {
    "model_check_error": ("T3", "T6", ""),
    "simulate_error": ("T2", "T5", ""),
    "semantic_regression": ("T4", "T5", ""),
    "constraint_violation": ("T4", "T5", ""),
    "numerical_instability": ("T2", "T5", ""),
}


def _norm_path(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return str(path.resolve())


def _derived_task_id(row: dict, index: int) -> str:
    case_id = str(row.get("case_id") or "").strip()
    if case_id:
        return f"repair_playbook_{case_id}"
    mutated = Path(str(row.get("mutated_model_path") or f"case_{index:03d}")).stem
    return f"repair_playbook_{mutated}"


def _taxonomy_ids(failure_type: str) -> tuple[str, str, str]:
    return _FAILURE_TO_TAXONOMY.get(str(failure_type or "").strip().lower(), ("T1", "T5", ""))


def _iter_source_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = load_json(str(path))
    rows: list[dict] = []
    if isinstance(payload.get("rows"), list):
        rows = [row for row in payload["rows"] if isinstance(row, dict)]
    elif isinstance(payload.get("tasks"), list):
        rows = [row for row in payload["tasks"] if isinstance(row, dict)]
    return rows


def load_real_case_bank_v191(
    *,
    case_bank_path: str = str(DEFAULT_CASE_BANK_PATH),
    limit: int = DEFAULT_CASE_BANK_SIZE,
) -> list[dict]:
    selected: list[dict] = []
    seen_mutated_paths: set[str] = set()
    requested_limit = max(0, int(limit))
    candidate_paths = [Path(case_bank_path)] if str(case_bank_path).strip() else []
    for path in DEFAULT_CASE_BANK_PATHS:
        if path not in candidate_paths:
            candidate_paths.append(path)

    for path in candidate_paths:
        for row in _iter_source_rows(path):
            failure_type = str(row.get("failure_type") or "").strip().lower()
            expected_stage = str(row.get("expected_stage") or "").strip().lower()
            source_model_path = _norm_path(str(row.get("source_model_path") or ""))
            mutated_model_path = _norm_path(str(row.get("mutated_model_path") or ""))
            if not (failure_type and expected_stage and source_model_path and mutated_model_path):
                continue
            if not (Path(source_model_path).exists() and Path(mutated_model_path).exists()):
                continue
            if mutated_model_path in seen_mutated_paths:
                continue
            seen_mutated_paths.add(mutated_model_path)
            selected.append(
                dict(
                    row,
                    failure_type=failure_type,
                    expected_stage=expected_stage,
                    source_model_path=source_model_path,
                    mutated_model_path=mutated_model_path,
                )
            )
            if len(selected) >= requested_limit:
                break
        if len(selected) >= requested_limit:
            break

    normalized: list[dict] = []
    for index, row in enumerate(selected, start=1):
        failure_type = str(row.get("failure_type") or "").strip().lower()
        expected_stage = str(row.get("expected_stage") or "").strip().lower()
        source_model_path = _norm_path(str(row.get("source_model_path") or ""))
        mutated_model_path = _norm_path(str(row.get("mutated_model_path") or ""))
        task_id = _derived_task_id(row, index)
        surface_tid, residual_tid, third_tid = _taxonomy_ids(failure_type)
        normalized.append(
            {
                "candidate_id": f"cmp_{index:03d}",
                "task_id": task_id,
                "source_case_id": str(row.get("case_id") or ""),
                "source_model_path": source_model_path,
                "mutated_model_path": mutated_model_path,
                "failure_type": failure_type,
                "expected_stage": expected_stage,
                "scale": str(row.get("scale") or ""),
                "workflow_goal": "repair_model",
                "planner_backend": "gemini",
                "backend": "openmodelica_docker",
                "surface_layer_taxonomy_id": surface_tid,
                "residual_layer_taxonomy_id": residual_tid,
                "optional_third_layer_taxonomy_id": third_tid,
            }
        )
    return normalized


__all__ = [
    "DEFAULT_CASE_BANK_PATH",
    "DEFAULT_CASE_BANK_PATHS",
    "DEFAULT_CASE_BANK_SIZE",
    "load_real_case_bank_v191",
]
