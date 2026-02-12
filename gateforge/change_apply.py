from __future__ import annotations

import hashlib
import json
from pathlib import Path

CHANGE_SET_SCHEMA_VERSION = "0.1.0"
SUPPORTED_OPS = {"replace_text"}


def load_change_set(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_change_set(payload)
    return payload


def validate_change_set(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("change_set must be a JSON object")
    if payload.get("schema_version") != CHANGE_SET_SCHEMA_VERSION:
        raise ValueError(f"change_set schema_version must be {CHANGE_SET_SCHEMA_VERSION}")
    changes = payload.get("changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("change_set changes must be a non-empty list")
    for idx, change in enumerate(changes):
        if not isinstance(change, dict):
            raise ValueError(f"change[{idx}] must be an object")
        op = change.get("op")
        if op not in SUPPORTED_OPS:
            raise ValueError(f"unsupported change op at index {idx}: {op}")
        file_path = change.get("file")
        old_text = change.get("old")
        new_text = change.get("new")
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError(f"change[{idx}].file must be a non-empty string")
        if not isinstance(old_text, str):
            raise ValueError(f"change[{idx}].old must be a string")
        if not isinstance(new_text, str):
            raise ValueError(f"change[{idx}].new must be a string")


def apply_change_set(path: str, workspace_root: Path) -> dict:
    raw_text = Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw_text)
    validate_change_set(payload)
    applied_changes: list[dict] = []

    for idx, change in enumerate(payload["changes"]):
        rel_path = Path(change["file"])
        if rel_path.is_absolute():
            raise ValueError(f"change[{idx}] file must be relative: {rel_path}")
        target = (workspace_root / rel_path).resolve()
        if workspace_root.resolve() not in target.parents and target != workspace_root.resolve():
            raise ValueError(f"change[{idx}] file escapes workspace: {rel_path}")
        if not target.exists():
            raise ValueError(f"change[{idx}] target file not found: {rel_path}")
        original = target.read_text(encoding="utf-8")
        old_text = change["old"]
        new_text = change["new"]
        if old_text not in original:
            raise ValueError(f"change[{idx}] old text not found in {rel_path}")
        replaced = original.replace(old_text, new_text, 1)
        target.write_text(replaced, encoding="utf-8")
        applied_changes.append(
            {
                "op": change["op"],
                "file": str(rel_path),
                "replaced_preview": old_text[:60],
            }
        )

    return {
        "change_set_hash": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "applied_changes": applied_changes,
    }
