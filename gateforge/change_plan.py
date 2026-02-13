from __future__ import annotations

from pathlib import Path

from .change_apply import CHANGE_SET_SCHEMA_VERSION, validate_change_set

CHANGE_PLAN_SCHEMA_VERSION = "0.1.0"
SUPPORTED_KINDS = {"replace_text"}


def validate_change_plan(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("change_plan must be a JSON object")
    if payload.get("schema_version") != CHANGE_PLAN_SCHEMA_VERSION:
        raise ValueError(f"change_plan schema_version must be {CHANGE_PLAN_SCHEMA_VERSION}")
    operations = payload.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValueError("change_plan operations must be a non-empty list")
    for idx, op in enumerate(operations):
        if not isinstance(op, dict):
            raise ValueError(f"change_plan operation[{idx}] must be an object")
        kind = op.get("kind")
        if kind not in SUPPORTED_KINDS:
            raise ValueError(f"unsupported change_plan kind at index {idx}: {kind}")
        file_path = op.get("file")
        old_text = op.get("old")
        new_text = op.get("new")
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError(f"change_plan operation[{idx}].file must be a non-empty string")
        if Path(file_path).is_absolute():
            raise ValueError(f"change_plan operation[{idx}].file must be relative")
        if not isinstance(old_text, str):
            raise ValueError(f"change_plan operation[{idx}].old must be a string")
        if not isinstance(new_text, str):
            raise ValueError(f"change_plan operation[{idx}].new must be a string")


def materialize_change_set_from_plan(change_plan: dict) -> dict:
    validate_change_plan(change_plan)
    changes = []
    for op in change_plan["operations"]:
        if op["kind"] == "replace_text":
            changes.append(
                {
                    "op": "replace_text",
                    "file": op["file"],
                    "old": op["old"],
                    "new": op["new"],
                }
            )
    payload = {
        "schema_version": CHANGE_SET_SCHEMA_VERSION,
        "changes": changes,
    }
    validate_change_set(payload)
    return payload

