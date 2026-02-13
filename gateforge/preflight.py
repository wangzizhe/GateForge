from __future__ import annotations

from pathlib import Path


def preflight_change_set(
    *,
    change_set: dict,
    workspace_root: Path,
    allowed_roots: list[str] | None = None,
    max_changes: int = 20,
) -> dict:
    reasons: list[str] = []
    hints: list[str] = []
    targets: list[str] = []

    root = workspace_root.resolve()
    allowed_prefixes = allowed_roots or ["examples/openmodelica"]
    changes = change_set.get("changes", [])
    if not isinstance(changes, list):
        return {
            "ok": False,
            "status": "failed",
            "reasons": ["change_preflight_invalid_changes"],
            "hints": ["change_set.changes must be a list."],
            "targets": [],
        }

    if len(changes) > max_changes:
        reasons.append("change_preflight_too_many_changes")
        hints.append(f"Change-set has {len(changes)} changes; limit is {max_changes}.")

    for idx, change in enumerate(changes):
        rel = str(change.get("file", "")).strip()
        if not rel:
            reasons.append("change_preflight_invalid_target")
            hints.append(f"change[{idx}] has empty file path.")
            continue
        targets.append(rel)
        rel_path = Path(rel)
        if rel_path.is_absolute():
            reasons.append("change_preflight_unsafe_scope")
            hints.append(f"change[{idx}] uses absolute path: {rel}")
            continue
        target = (root / rel_path).resolve()
        if root not in target.parents and target != root:
            reasons.append("change_preflight_unsafe_scope")
            hints.append(f"change[{idx}] escapes workspace: {rel}")
            continue
        if not any(rel.startswith(prefix + "/") or rel == prefix for prefix in allowed_prefixes):
            reasons.append("change_preflight_disallowed_path")
            hints.append(f"change[{idx}] path is outside allowed roots: {rel}")
        if target.suffix not in {".mo", ".mos"}:
            reasons.append("change_preflight_disallowed_filetype")
            hints.append(f"change[{idx}] file extension is not allowed: {target.suffix}")
        if not target.exists():
            reasons.append("change_preflight_target_not_found")
            hints.append(f"change[{idx}] target file not found: {rel}")

    dedup_reasons = list(dict.fromkeys(reasons))
    dedup_hints = list(dict.fromkeys(hints))
    return {
        "ok": not dedup_reasons,
        "status": "passed" if not dedup_reasons else "failed",
        "reasons": dedup_reasons,
        "hints": dedup_hints,
        "targets": targets,
    }

