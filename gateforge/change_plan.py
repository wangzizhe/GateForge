from __future__ import annotations

import statistics
from pathlib import Path

from .change_apply import CHANGE_SET_SCHEMA_VERSION, validate_change_set

CHANGE_PLAN_SCHEMA_VERSION = "0.1.0"
SUPPORTED_KINDS = {"replace_text"}
DEFAULT_ALLOWED_ROOTS = ("examples/openmodelica",)
DEFAULT_ALLOWED_SUFFIXES = (".mo", ".mos")


def validate_change_plan(
    payload: dict,
    *,
    allowed_roots: tuple[str, ...] = DEFAULT_ALLOWED_ROOTS,
    allowed_suffixes: tuple[str, ...] = DEFAULT_ALLOWED_SUFFIXES,
    max_ops: int = 20,
    max_chars_per_op: int = 4000,
) -> None:
    if not isinstance(payload, dict):
        raise ValueError("change_plan must be a JSON object")
    if payload.get("schema_version") != CHANGE_PLAN_SCHEMA_VERSION:
        raise ValueError(f"change_plan schema_version must be {CHANGE_PLAN_SCHEMA_VERSION}")
    operations = payload.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValueError("change_plan operations must be a non-empty list")
    if len(operations) > max_ops:
        raise ValueError(f"change_plan operations length {len(operations)} exceeds max_ops={max_ops}")
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
        if not any(file_path == root or file_path.startswith(root + "/") for root in allowed_roots):
            raise ValueError(f"change_plan operation[{idx}].file outside allowed roots: {file_path}")
        if not file_path.endswith(allowed_suffixes):
            raise ValueError(
                f"change_plan operation[{idx}].file must end with one of {sorted(allowed_suffixes)}"
            )
        if not isinstance(old_text, str):
            raise ValueError(f"change_plan operation[{idx}].old must be a string")
        if not isinstance(new_text, str):
            raise ValueError(f"change_plan operation[{idx}].new must be a string")
        if len(old_text) > max_chars_per_op or len(new_text) > max_chars_per_op:
            raise ValueError(
                f"change_plan operation[{idx}] old/new text exceeds max_chars_per_op={max_chars_per_op}"
            )
        reason = op.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"change_plan operation[{idx}].reason must be a non-empty string")
        confidence = op.get("confidence")
        if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
            raise ValueError(f"change_plan operation[{idx}].confidence must be in [0.0, 1.0]")


def materialize_change_set_from_plan(change_plan: dict) -> dict:
    validate_change_plan(change_plan)
    stats = summarize_change_plan(change_plan)
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
        "metadata": {
            "source": "change_plan",
            "plan_ops_count": stats["plan_ops_count"],
            "plan_confidence_min": stats["plan_confidence_min"],
            "plan_confidence_avg": stats["plan_confidence_avg"],
            "plan_confidence_max": stats["plan_confidence_max"],
        },
    }
    validate_change_set(payload)
    return payload


def summarize_change_plan(change_plan: dict) -> dict:
    validate_change_plan(change_plan)
    confidences = [float(op["confidence"]) for op in change_plan["operations"]]
    return {
        "plan_ops_count": len(confidences),
        "plan_confidence_min": min(confidences),
        "plan_confidence_avg": float(statistics.mean(confidences)),
        "plan_confidence_max": max(confidences),
    }
