from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_benchmark_schema_v0_29_0 import validate_benchmark_task

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_benchmark_task(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    try:
        task = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(task, dict):
        return None
    return task


def load_benchmark_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    if not manifest_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def load_and_validate_task(task_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    task = load_benchmark_task(task_path)
    if task is None:
        return None, [f"failed_to_load:{task_path}"]
    errors = validate_benchmark_task(task)
    return task, errors
