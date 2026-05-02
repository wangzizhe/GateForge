from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent

FAIL_VERDICTS = {"FAILED", "FAIL", "ERROR", "TIMEOUT"}


def _descriptor(payload: dict[str, Any], path: Path) -> str:
    provider = str(payload.get("provider") or payload.get("provider_backend") or "provider")
    model = str(payload.get("model") or payload.get("planner_model") or "model")
    profile = str(payload.get("tool_profile") or payload.get("profile") or "tool-use")
    budget = str(payload.get("max_token_budget") or payload.get("token_budget") or "budget")
    version = str(payload.get("version") or path.parent.name)
    return f"{provider} / {model} / {profile} / {budget} / {version}"


def _add(mapping: dict[str, set[str]], case_id: str, descriptor: str) -> None:
    if not case_id:
        return
    mapping.setdefault(case_id, set()).add(descriptor)


def mine_known_hard_from_summary(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    descriptor = _descriptor(payload, path)
    mapping: dict[str, set[str]] = {}
    sibling_results = path.with_name("results.jsonl")
    row_mapping = (
        mine_known_hard_from_results_jsonl(sibling_results, fallback_summary=payload)
        if sibling_results.exists()
        else {}
    )
    cases = payload.get("cases")
    if isinstance(cases, list):
        for case in cases:
            if not isinstance(case, dict):
                continue
            case_id = str(case.get("case_id") or "")
            verdict_values = [
                str(value)
                for key, value in case.items()
                if key.endswith("verdict") or key in {"status", "result"}
            ]
            if str(case.get("delta") or "") == "stable_fail":
                _add(mapping, case_id, descriptor)
            elif verdict_values and all(value.upper() in FAIL_VERDICTS for value in verdict_values):
                _add(mapping, case_id, descriptor)
            elif str(case.get("final_verdict") or "").upper() in FAIL_VERDICTS:
                _add(mapping, case_id, descriptor)
    case_ids = payload.get("case_ids")
    if (
        isinstance(case_ids, list)
        and int(payload.get("case_count") or len(case_ids)) > 0
        and int(payload.get("pass_count") or 0) == 0
        and int(payload.get("provider_error_count") or 0) == 0
        and int(payload.get("load_error_count") or 0) == 0
        and not row_mapping
    ):
        for case_id in case_ids:
            _add(mapping, str(case_id), descriptor)
    for case_id, descriptors in row_mapping.items():
        for descriptor in descriptors:
            _add(mapping, case_id, descriptor)
    return {case_id: sorted(values) for case_id, values in sorted(mapping.items())}


def mine_known_hard_from_results_jsonl(
    path: Path,
    *,
    fallback_summary: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    fallback = fallback_summary or {}
    mapping: dict[str, set[str]] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if str(row.get("provider_error") or "").strip():
            continue
        case_id = str(row.get("case_id") or "")
        verdict = str(row.get("final_verdict") or row.get("verdict") or row.get("status") or "").upper()
        if verdict not in FAIL_VERDICTS:
            continue
        descriptor_payload = dict(fallback)
        descriptor_payload.update({key: value for key, value in row.items() if value not in (None, "", [])})
        _add(mapping, case_id, _descriptor(descriptor_payload, path))
    return {case_id: sorted(values) for case_id, values in sorted(mapping.items())}


def merge_known_hard_maps(*maps: dict[str, list[str]]) -> dict[str, list[str]]:
    merged: dict[str, set[str]] = {}
    for mapping in maps:
        for case_id, descriptors in mapping.items():
            for descriptor in descriptors:
                if str(descriptor).strip():
                    merged.setdefault(case_id, set()).add(str(descriptor))
    return {case_id: sorted(values) for case_id, values in sorted(merged.items())}


def mine_known_hard_from_artifacts(paths: list[Path]) -> dict[str, list[str]]:
    return merge_known_hard_maps(*(mine_known_hard_from_summary(path) for path in paths))
