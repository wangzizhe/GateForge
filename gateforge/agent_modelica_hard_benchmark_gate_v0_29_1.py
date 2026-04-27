from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_benchmark_loader_v0_29_0 import load_and_validate_task

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASK_ROOT = REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "tasks"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_benchmark_gate_v0_29_1"

LEAKY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bdeficit\s*=\s*\d+", re.IGNORECASE),
    re.compile(r"\bmissing equation", re.IGNORECASE),
    re.compile(r"\bmissing variables?", re.IGNORECASE),
    re.compile(r"\bwithout equations?", re.IGNORECASE),
    re.compile(r"\bno defining equations?", re.IGNORECASE),
    re.compile(r"\bsubscript out of bounds", re.IGNORECASE),
    re.compile(r"\bindex\s+\d+", re.IGNORECASE),
    re.compile(r"\bfix both\b", re.IGNORECASE),
    re.compile(r"\bfix all\b", re.IGNORECASE),
    re.compile(r"\bomc only reports\b", re.IGNORECASE),
)

WORKFLOW_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\brefactor", re.IGNORECASE),
    re.compile(r"\bmigrat", re.IGNORECASE),
    re.compile(r"\bparameteri[sz]", re.IGNORECASE),
    re.compile(r"\bpreserve behavior", re.IGNORECASE),
    re.compile(r"\bworkflow", re.IGNORECASE),
    re.compile(r"\binterface", re.IGNORECASE),
    re.compile(r"\breplace", re.IGNORECASE),
    re.compile(r"\bextend", re.IGNORECASE),
    re.compile(r"\bconstraint", re.IGNORECASE),
    re.compile(r"\btopolog", re.IGNORECASE),
    re.compile(r"\bconnect", re.IGNORECASE),
)

MODEL_COMPLEXITY_PATTERNS: dict[str, re.Pattern[str]] = {
    "msl_component": re.compile(r"Modelica\.", re.IGNORECASE),
    "connect": re.compile(r"\bconnect\s*\(", re.IGNORECASE),
    "stateful_component": re.compile(r"\b(Capacitor|Inductor)\b", re.IGNORECASE),
    "array": re.compile(r"\[[^\]]+\]"),
    "conditional": re.compile(r"\b(if|when)\b", re.IGNORECASE),
    "inheritance_or_replaceable": re.compile(r"\b(extends|replaceable|redeclare)\b", re.IGNORECASE),
}


def _joined_prompt_text(task: dict[str, Any]) -> str:
    parts = [
        str(task.get("title") or ""),
        str(task.get("description") or ""),
        "\n".join(str(item) for item in task.get("constraints") or []),
    ]
    return "\n".join(parts)


def _count_matches(pattern: re.Pattern[str], text: str) -> int:
    return len(pattern.findall(text or ""))


def _has_behavioral_oracle(task: dict[str, Any]) -> bool:
    verification = task.get("verification")
    if not isinstance(verification, dict):
        return False
    return isinstance(verification.get("behavioral"), dict)


def _benchmark_focus(task: dict[str, Any]) -> str:
    return str(task.get("benchmark_focus") or "").strip().lower()


def _model_complexity_features(model_text: str) -> dict[str, int | bool]:
    feature_counts = {
        name: _count_matches(pattern, model_text)
        for name, pattern in MODEL_COMPLEXITY_PATTERNS.items()
    }
    declaration_count = len(re.findall(r"^\s*(Real|parameter|input|output)\b", model_text, re.MULTILINE))
    equation_count = len(re.findall(r"^\s*[^/\s][^;]*;", model_text, re.MULTILINE))
    score = 0
    score += 1 if feature_counts["msl_component"] >= 3 else 0
    score += 1 if feature_counts["connect"] >= 3 else 0
    score += 1 if feature_counts["stateful_component"] >= 1 else 0
    score += 1 if feature_counts["array"] >= 1 else 0
    score += 1 if feature_counts["conditional"] >= 1 else 0
    score += 1 if feature_counts["inheritance_or_replaceable"] >= 1 else 0
    score += 1 if declaration_count >= 5 else 0
    score += 1 if equation_count >= 6 else 0
    return {
        **feature_counts,
        "declaration_count": declaration_count,
        "equation_count": equation_count,
        "complexity_score": score,
    }


def audit_hard_benchmark_task(task: dict[str, Any]) -> dict[str, Any]:
    prompt_text = _joined_prompt_text(task)
    model_text = str(task.get("initial_model") or "")
    leaky_matches = sorted(
        {pattern.pattern for pattern in LEAKY_PATTERNS if pattern.search(prompt_text)}
    )
    workflow_matches = sorted(
        {pattern.pattern for pattern in WORKFLOW_PATTERNS if pattern.search(prompt_text)}
    )
    complexity = _model_complexity_features(model_text)
    has_behavioral_oracle = _has_behavioral_oracle(task)
    model_check_first = _benchmark_focus(task) == "model_check_structural"
    is_complex = str(task.get("difficulty") or "") == "complex"
    source_backed = bool(task.get("source_backed"))
    workflow_proximal = bool(workflow_matches)
    root_cause_hidden = not leaky_matches
    complexity_ready = int(complexity["complexity_score"]) >= 3
    boundary_ready = all(
        (
            is_complex,
            source_backed,
            root_cause_hidden,
            workflow_proximal,
            complexity_ready,
            has_behavioral_oracle or model_check_first,
        )
    )
    blockers: list[str] = []
    if not is_complex:
        blockers.append("not_complex")
    if not source_backed:
        blockers.append("not_source_backed")
    if not root_cause_hidden:
        blockers.append("root_cause_leaked_in_prompt")
    if not workflow_proximal:
        blockers.append("not_workflow_proximal")
    if not complexity_ready:
        blockers.append("model_complexity_too_low")
    if not has_behavioral_oracle and not model_check_first:
        blockers.append("missing_behavioral_oracle")
    return {
        "case_id": str(task.get("case_id") or ""),
        "task_type": str(task.get("task_type") or ""),
        "difficulty": str(task.get("difficulty") or ""),
        "source_backed": source_backed,
        "root_cause_hidden": root_cause_hidden,
        "workflow_proximal": workflow_proximal,
        "has_behavioral_oracle": has_behavioral_oracle,
        "benchmark_focus": _benchmark_focus(task),
        "model_check_first": model_check_first,
        "complexity": complexity,
        "leaky_prompt_patterns": leaky_matches,
        "workflow_patterns": workflow_matches,
        "boundary_ready": boundary_ready,
        "blockers": blockers,
    }


def iter_task_paths(task_root: Path) -> list[Path]:
    if task_root.is_file():
        return [task_root]
    if not task_root.exists():
        return []
    return sorted(path for path in task_root.rglob("*.json") if path.is_file())


def run_hard_benchmark_gate(
    *,
    task_root: Path = DEFAULT_TASK_ROOT,
    out_dir: Path = DEFAULT_OUT_DIR,
    case_id_prefix: str = "",
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    validation_errors: dict[str, list[str]] = {}
    for path in iter_task_paths(task_root):
        task, errors = load_and_validate_task(path)
        if task is None:
            validation_errors[str(path)] = errors
            continue
        case_id = str(task.get("case_id") or "")
        if case_id_prefix and not case_id.startswith(case_id_prefix):
            continue
        if errors:
            validation_errors[case_id or str(path)] = errors
            continue
        row = audit_hard_benchmark_task(task)
        row["path"] = str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)
        rows.append(row)

    ready_rows = [row for row in rows if row.get("boundary_ready")]
    blocker_counts: dict[str, int] = {}
    for row in rows:
        for blocker in row.get("blockers", []):
            blocker_counts[str(blocker)] = blocker_counts.get(str(blocker), 0) + 1

    summary = {
        "version": "v0.29.1",
        "status": "PASS" if rows and not validation_errors else "REVIEW",
        "analysis_scope": "hard_benchmark_gate",
        "task_root": str(task_root.relative_to(REPO_ROOT)) if task_root.is_relative_to(REPO_ROOT) else str(task_root),
        "case_id_prefix": case_id_prefix,
        "task_count": len(rows),
        "boundary_ready_count": len(ready_rows),
        "validation_error_count": len(validation_errors),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "decision": (
            "hard_benchmark_candidates_ready"
            if ready_rows
            else "hard_benchmark_candidates_need_redesign"
        ),
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "llm_capability_gain_claimed": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary, rows=rows, validation_errors=validation_errors)
    return summary


def write_outputs(
    *,
    out_dir: Path,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    validation_errors: dict[str, list[str]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "task_audit.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "validation_errors.json").write_text(
        json.dumps(validation_errors, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
