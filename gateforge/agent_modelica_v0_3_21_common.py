from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_omc_workspace_v1 import run_omc_script_docker, temporary_workspace
from .agent_modelica_v0_3_19_common import DOCKER_IMAGE
from .agent_modelica_v0_3_20_common import (
    DUAL_RECHECK_SPECS as V0320_DUAL_RECHECK_SPECS,
    SINGLE_MISMATCH_SPECS as V0320_SINGLE_MISMATCH_SPECS,
    build_dual_task_rows as build_v0320_dual_task_rows,
    build_single_task_rows as build_v0320_single_task_rows,
    first_attempt_signature,
    load_json,
    norm,
    rerun_once,
    replacement_audit,
    run_synthetic_task_live,
    write_json,
    write_text,
)


SCHEMA_PREFIX = "agent_modelica_v0_3_21"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SURFACE_INDEX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_21_surface_index_current"
DEFAULT_TASKSET_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_21_taskset_current"
DEFAULT_FIRST_FIX_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_21_first_fix_results_current"
DEFAULT_FIRST_FIX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_21_first_fix_evidence_current"
DEFAULT_DUAL_RECHECK_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_21_dual_recheck_results_current"
DEFAULT_DUAL_RECHECK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_21_dual_recheck_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_21_closeout_current"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


DISCOVERY_SURFACE_QUERY_SPEC = {
    "class_packages": {
        "Modelica.Blocks.Source.Sine": "Modelica.Blocks.Sources",
        "Modelica.Blocks.Source.Step": "Modelica.Blocks.Sources",
        "Modelica.Thermal.HeatTransfer.Components.FixedTemperature": "Modelica.Thermal.HeatTransfer.Sources",
    },
    "parameter_classes": [
        "Modelica.Blocks.Sources.Sine",
        "Modelica.Blocks.Sources.Step",
        "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
    ],
}


SURFACE_INDEX_FIXTURE = {
    "source_mode": "fixture_fallback",
    "omc_backend": "openmodelica_docker",
    "docker_image": DOCKER_IMAGE,
    "modelica_version": "4.1.0",
    "class_path_candidates": {
        "Modelica.Blocks.Source.Sine": [
            "Modelica.Blocks.Sources.Sine",
            "Modelica.Blocks.Sources.Step",
            "Modelica.Blocks.Sources.Pulse",
        ],
        "Modelica.Blocks.Source.Step": [
            "Modelica.Blocks.Sources.Step",
            "Modelica.Blocks.Sources.Sine",
            "Modelica.Blocks.Sources.Pulse",
        ],
        "Modelica.Thermal.HeatTransfer.Components.FixedTemperature": [
            "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
            "Modelica.Thermal.HeatTransfer.Sources.PrescribedTemperature",
            "Modelica.Thermal.HeatTransfer.Sources.FixedHeatFlow",
        ],
    },
    "parameter_surface_records": {
        repr(("Modelica.Blocks.Sources.Sine", "freqHz")): [
            {"name": "amplitude", "comment": "Amplitude of sine wave"},
            {"name": "f", "comment": "Frequency of sine wave"},
            {"name": "phase", "comment": "Phase of sine wave"},
            {"name": "continuous", "comment": "Make output continuous"},
        ],
        repr(("Modelica.Blocks.Sources.Sine", "amp")): [
            {"name": "amplitude", "comment": "Amplitude of sine wave"},
            {"name": "f", "comment": "Frequency of sine wave"},
            {"name": "phase", "comment": "Phase of sine wave"},
            {"name": "continuous", "comment": "Make output continuous"},
        ],
        repr(("Modelica.Blocks.Sources.Step", "amplitude")): [
            {"name": "height", "comment": "Height of step"},
            {"name": "offset", "comment": "Offset of output signal"},
            {"name": "startTime", "comment": "Output = offset for time < startTime"},
        ],
        repr(("Modelica.Blocks.Sources.Step", "startT")): [
            {"name": "height", "comment": "Height of step"},
            {"name": "offset", "comment": "Offset of output signal"},
            {"name": "startTime", "comment": "Output = offset for time < startTime"},
        ],
        repr(("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "temperature")): [
            {"name": "T", "comment": "Fixed temperature at port"},
        ],
    },
}


TOKEN_EXPANSIONS = {
    "freq": ["frequency", "hz", "f"],
    "freqhz": ["frequency", "hz", "f"],
    "amp": ["amplitude", "magnitude", "height"],
    "amplitude": ["amplitude", "magnitude", "height"],
    "startt": ["start", "time", "starttime"],
    "temperature": ["temperature", "t"],
    "temp": ["temperature", "t"],
}


def _omc_eval(expr: str, timeout_sec: int = 120) -> str:
    script = "\n".join(
        [
            "loadModel(Modelica);",
            f"{expr};",
            "getErrorString();",
            "",
        ]
    )
    with temporary_workspace("v0321_surface_") as td:
        rc, output = run_omc_script_docker(
            script_text=script,
            timeout_sec=timeout_sec,
            cwd=td,
            image=DOCKER_IMAGE,
        )
    if rc != 0:
        return ""
    lines = [line.strip() for line in str(output or "").splitlines() if line.strip()]
    if len(lines) >= 3:
        return "\n".join(lines[1:-1])
    if len(lines) >= 2:
        return lines[1]
    return ""


def _strip_quotes(text: str) -> str:
    value = norm(text)
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def _split_top_level(text: str) -> list[str]:
    items: list[str] = []
    buf: list[str] = []
    depth = 0
    in_string = False
    escape = False
    for ch in str(text or ""):
        if in_string:
            buf.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            buf.append(ch)
            continue
        if ch == "{":
            depth += 1
            buf.append(ch)
            continue
        if ch == "}":
            depth = max(0, depth - 1)
            buf.append(ch)
            continue
        if ch == "," and depth == 0:
            token = "".join(buf).strip()
            if token:
                items.append(token)
            buf = []
            continue
        buf.append(ch)
    token = "".join(buf).strip()
    if token:
        items.append(token)
    return items


def _unwrap_braces(text: str) -> str:
    value = norm(text)
    if value.startswith("{") and value.endswith("}"):
        return value[1:-1]
    return value


def _parse_class_names(payload_text: str) -> list[str]:
    inner = _unwrap_braces(payload_text)
    raw_items = _split_top_level(inner)
    return [norm(item) for item in raw_items if norm(item)]


def _parse_component_records(payload_text: str) -> list[dict]:
    inner = _unwrap_braces(payload_text)
    rows: list[dict] = []
    for item in _split_top_level(inner):
        record_inner = _unwrap_braces(item)
        parts = _split_top_level(record_inner)
        if len(parts) < 9:
            continue
        variability = _strip_quotes(parts[8])
        if variability != "parameter":
            continue
        rows.append(
            {
                "declared_type": norm(parts[0]),
                "name": norm(parts[1]),
                "comment": _strip_quotes(parts[2]),
            }
        )
    return rows


def _omc_list_class(class_name: str, timeout_sec: int = 120) -> str:
    payload = _omc_eval(f"list({class_name})", timeout_sec=timeout_sec)
    return _strip_quotes(payload)


def _parse_parameter_records_from_listing(listing: str) -> list[dict]:
    rows: list[dict] = []
    for raw_line in str(listing or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("parameter "):
            continue
        match = re.search(
            r"parameter\s+.+?\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^)]*\))?\s*(?:=\s*[^\";]+)?(?:\s+\"([^\"]*)\")?",
            line,
        )
        if not match:
            continue
        rows.append(
            {
                "name": norm(match.group(1)),
                "comment": norm(match.group(2)),
            }
        )
    return rows


def _parse_extends_targets(listing: str) -> list[str]:
    targets: list[str] = []
    for raw_line in str(listing or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("extends "):
            continue
        match = re.match(r"extends\s+([A-Za-z0-9_\.]+)", line)
        if match:
            targets.append(norm(match.group(1)))
    return targets


def _resolve_relative_class_name(current_class: str, target: str) -> str:
    candidate = norm(target)
    if not candidate or candidate.startswith("Modelica."):
        return candidate
    current_parts = norm(current_class).split(".")[:-1]
    target_parts = candidate.split(".")
    for width in range(len(current_parts), 0, -1):
        probe = ".".join(current_parts[:width] + target_parts)
        listing = _omc_list_class(probe)
        if listing and "Error" not in listing:
            return probe
    return candidate


def _merge_parameter_records(primary: list[dict], extra: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in list(primary or []) + list(extra or []):
        name = norm(row.get("name"))
        if not name:
            continue
        current = merged.get(name) or {"name": name, "comment": ""}
        comment = norm(row.get("comment")) or norm(current.get("comment"))
        merged[name] = {"name": name, "comment": comment}
    return list(merged.values())


def _collect_parameter_surface(class_name: str, visited: set[str] | None = None) -> list[dict]:
    seen = set(visited or set())
    name = norm(class_name)
    if not name or name in seen:
        return []
    seen.add(name)
    direct = _parse_component_records(_omc_eval(f"getComponents({name})"))
    listing = _omc_list_class(name)
    local = _parse_parameter_records_from_listing(listing)
    merged = _merge_parameter_records(direct, local)
    for parent in _parse_extends_targets(listing):
        resolved_parent = _resolve_relative_class_name(name, parent)
        merged = _merge_parameter_records(merged, _collect_parameter_surface(resolved_parent, seen))
    return merged


def _try_build_surface_index_from_omc() -> dict:
    modelica_version = _strip_quotes(_omc_eval("getVersion(Modelica)"))
    class_path_candidates: dict[str, list[str]] = {}
    parameter_surface_records: dict[str, list[dict]] = {}
    for wrong_symbol, package_name in (DISCOVERY_SURFACE_QUERY_SPEC.get("class_packages") or {}).items():
        payload = _omc_eval(f"getClassNames({package_name})")
        class_names = _parse_class_names(payload)
        if not class_names:
            return {}
        class_path_candidates[wrong_symbol] = [f"{package_name}.{name}" for name in class_names]
    for class_name in DISCOVERY_SURFACE_QUERY_SPEC.get("parameter_classes") or []:
        rows = _collect_parameter_surface(class_name)
        if not rows:
            return {}
        wrong_keys = [
            repr((class_name, "freqHz")),
            repr((class_name, "amp")),
            repr((class_name, "amplitude")),
            repr((class_name, "startT")),
            repr((class_name, "temperature")),
        ]
        for wrong_key in wrong_keys:
            parameter_surface_records[wrong_key] = rows
    return {
        "source_mode": "omc_export",
        "omc_backend": "openmodelica_docker",
        "docker_image": DOCKER_IMAGE,
        "modelica_version": modelica_version or "unknown",
        "class_path_candidates": class_path_candidates,
        "parameter_surface_records": parameter_surface_records,
    }


def build_surface_index_payload(*, use_fixture_only: bool = False) -> dict:
    if use_fixture_only:
        return dict(SURFACE_INDEX_FIXTURE)
    live = _try_build_surface_index_from_omc()
    if live:
        return live
    return dict(SURFACE_INDEX_FIXTURE)


def _split_identifier_tokens(text: str) -> list[str]:
    raw = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", norm(text))
    chunks = re.split(r"[^A-Za-z0-9]+", raw)
    tokens: list[str] = []
    for chunk in chunks:
        if not chunk:
            continue
        lowered = chunk.lower()
        tokens.append(lowered)
        tokens.extend(TOKEN_EXPANSIONS.get(lowered, []))
    return [token for token in tokens if token]


def _leaf_name(class_path: str) -> str:
    value = norm(class_path)
    return value.rsplit(".", 1)[-1] if "." in value else value


def _shared_count(a: list[str], b: list[str]) -> int:
    return len(set(a) & set(b))


def rank_class_path_candidates(*, wrong_symbol: str, candidates: list[str]) -> list[dict]:
    wrong_leaf = _leaf_name(wrong_symbol).lower()
    wrong_pkg_tokens = _split_identifier_tokens(wrong_symbol.rsplit(".", 1)[0] if "." in wrong_symbol else wrong_symbol)
    rows: list[dict] = []
    for idx, candidate in enumerate(candidates):
        candidate_leaf = _leaf_name(candidate).lower()
        candidate_pkg_tokens = _split_identifier_tokens(candidate.rsplit(".", 1)[0] if "." in candidate else candidate)
        score = 0
        if candidate_leaf == wrong_leaf:
            score += 100
        if wrong_leaf and candidate_leaf.startswith(wrong_leaf):
            score += 20
        score += 10 * _shared_count(wrong_pkg_tokens, candidate_pkg_tokens)
        rows.append(
            {
                "candidate": candidate,
                "score": score,
                "rank_features": {
                    "leaf_exact_match": candidate_leaf == wrong_leaf,
                    "package_token_overlap": _shared_count(wrong_pkg_tokens, candidate_pkg_tokens),
                    "input_order": idx,
                },
            }
        )
    rows.sort(key=lambda row: (-int(row.get("score") or 0), int((row.get("rank_features") or {}).get("input_order") or 0), norm(row.get("candidate"))))
    return rows


def rank_parameter_candidates(*, wrong_symbol: str, candidate_records: list[dict]) -> list[dict]:
    wrong_tokens = _split_identifier_tokens(wrong_symbol)
    rows: list[dict] = []
    for idx, record in enumerate(candidate_records):
        name = norm(record.get("name"))
        comment = norm(record.get("comment"))
        candidate_tokens = _split_identifier_tokens(f"{name} {comment}")
        token_overlap = _shared_count(wrong_tokens, candidate_tokens)
        score = 15 * token_overlap
        if any(token == name.lower() for token in wrong_tokens):
            score += 50
        if name.lower().startswith(norm(wrong_symbol).lower()):
            score += 10
        rows.append(
            {
                "candidate": name,
                "score": score,
                "comment": comment,
                "rank_features": {
                    "token_overlap": token_overlap,
                    "input_order": idx,
                },
            }
        )
    rows.sort(key=lambda row: (-int(row.get("score") or 0), int((row.get("rank_features") or {}).get("input_order") or 0), norm(row.get("candidate"))))
    return rows


def class_candidates_for(surface_index: dict, wrong_symbol: str) -> list[str]:
    candidates = surface_index.get("class_path_candidates") if isinstance(surface_index.get("class_path_candidates"), dict) else {}
    rows = candidates.get(norm(wrong_symbol))
    return [norm(item) for item in rows if norm(item)] if isinstance(rows, list) else []


def parameter_records_for(surface_index: dict, component_type: str, wrong_symbol: str) -> list[dict]:
    records = surface_index.get("parameter_surface_records") if isinstance(surface_index.get("parameter_surface_records"), dict) else {}
    rows = records.get(repr((norm(component_type), norm(wrong_symbol))))
    if not isinstance(rows, list):
        return []
    clean_rows: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        clean_rows.append({"name": norm(row.get("name")), "comment": norm(row.get("comment"))})
    return clean_rows


def apply_discovery_first_fix(
    *,
    current_text: str,
    patch_type: str,
    wrong_symbol: str,
    component_type: str,
    canonical_symbol: str,
    class_candidates: list[str] | None = None,
    parameter_records: list[dict] | None = None,
) -> tuple[str, dict]:
    current = str(current_text or "")
    if patch_type == "replace_class_path":
        candidates = [norm(item) for item in (class_candidates or []) if norm(item)]
        ranked = rank_class_path_candidates(wrong_symbol=wrong_symbol, candidates=candidates)
        selected = norm(ranked[0].get("candidate")) if ranked else ""
        if wrong_symbol not in current:
            return current, {
                "applied": False,
                "reason": "wrong_symbol_not_found_in_text",
                "selected_candidate": selected,
                "candidate_symbols": candidates,
                "candidate_contains_canonical": canonical_symbol in candidates,
                "candidate_top1_is_canonical": selected == canonical_symbol,
                "ranked_candidates": ranked,
            }
        if not selected:
            return current, {
                "applied": False,
                "reason": "candidate_set_empty",
                "selected_candidate": "",
                "candidate_symbols": candidates,
                "candidate_contains_canonical": canonical_symbol in candidates,
                "candidate_top1_is_canonical": False,
                "ranked_candidates": ranked,
            }
        patched = current.replace(wrong_symbol, selected, 1)
        return patched, {
            "applied": patched != current,
            "reason": "applied_discovery_patch" if patched != current else "text_unchanged_after_patch",
            "selected_candidate": selected,
            "candidate_symbols": candidates,
            "candidate_contains_canonical": canonical_symbol in candidates,
            "candidate_top1_is_canonical": selected == canonical_symbol,
            "ranked_candidates": ranked,
        }
    records = list(parameter_records or [])
    ranked = rank_parameter_candidates(wrong_symbol=wrong_symbol, candidate_records=records)
    selected = norm(ranked[0].get("candidate")) if ranked else ""
    candidates = [norm(row.get("name")) for row in records if norm(row.get("name"))]
    pattern = re.compile(rf"\b{re.escape(wrong_symbol)}\b(?=\s*=)")
    if not pattern.search(current):
        return current, {
            "applied": False,
            "reason": "wrong_symbol_not_found_in_parameter_binding",
            "selected_candidate": selected,
            "candidate_symbols": candidates,
            "candidate_contains_canonical": canonical_symbol in candidates,
            "candidate_top1_is_canonical": selected == canonical_symbol,
            "ranked_candidates": ranked,
        }
    if not selected:
        return current, {
            "applied": False,
            "reason": "candidate_set_empty",
            "selected_candidate": "",
            "candidate_symbols": candidates,
            "candidate_contains_canonical": canonical_symbol in candidates,
            "candidate_top1_is_canonical": False,
            "ranked_candidates": ranked,
        }
    patched = pattern.sub(selected, current, count=1)
    return patched, {
        "applied": patched != current,
        "reason": "applied_discovery_patch" if patched != current else "text_unchanged_after_patch",
        "selected_candidate": selected,
        "candidate_symbols": candidates,
        "candidate_contains_canonical": canonical_symbol in candidates,
        "candidate_top1_is_canonical": selected == canonical_symbol,
        "ranked_candidates": ranked,
    }


def build_v0321_single_task_rows(surface_index: dict) -> list[dict]:
    base_rows = build_v0320_single_task_rows()
    spec_by_task = {norm(spec.get("task_id")): spec for spec in V0320_SINGLE_MISMATCH_SPECS}
    rows: list[dict] = []
    for row in base_rows:
        spec = spec_by_task.get(norm(row.get("task_id"))) or {}
        patch_type = norm(row.get("patch_type"))
        component_type = norm(row.get("component_type"))
        wrong_symbol = norm(row.get("wrong_symbol"))
        canonical_symbol = norm(row.get("correct_symbol"))
        class_candidates = class_candidates_for(surface_index, wrong_symbol)
        parameter_records = parameter_records_for(surface_index, component_type, wrong_symbol)
        updated = dict(row)
        updated["discovery_mode"] = "authoritative_local_surface"
        updated["source_index_mode"] = norm(surface_index.get("source_mode"))
        updated["candidate_symbols"] = class_candidates if patch_type == "replace_class_path" else [norm(item.get("name")) for item in parameter_records]
        updated["candidate_parameter_records"] = parameter_records
        updated["class_path_candidates"] = class_candidates
        updated["candidate_generation_policy"] = "class_path_suffix_package_locality" if patch_type == "replace_class_path" else "component_type_exact_surface_then_comment_similarity"
        updated["surface_index_component"] = component_type
        updated["v0_3_21_spec"] = {
            "task_id": norm(spec.get("task_id")),
            "patch_type": patch_type,
            "wrong_symbol": wrong_symbol,
            "canonical_symbol": canonical_symbol,
        }
        rows.append(updated)
    return rows


def build_v0321_dual_task_rows(surface_index: dict) -> list[dict]:
    base_rows = build_v0320_dual_task_rows()
    spec_by_task = {norm(spec.get("task_id")): spec for spec in V0320_DUAL_RECHECK_SPECS}
    rows: list[dict] = []
    for row in base_rows:
        spec = spec_by_task.get(norm(row.get("task_id"))) or {}
        steps = []
        for base_step in row.get("repair_steps") if isinstance(row.get("repair_steps"), list) else []:
            patch_type = norm(base_step.get("patch_type"))
            component_type = norm(base_step.get("component_type"))
            wrong_symbol = norm(base_step.get("wrong_symbol"))
            canonical_symbol = norm(base_step.get("correct_symbol"))
            steps.append(
                {
                    **dict(base_step),
                    "class_path_candidates": class_candidates_for(surface_index, wrong_symbol),
                    "candidate_parameter_records": parameter_records_for(surface_index, component_type, wrong_symbol),
                    "candidate_generation_policy": "class_path_suffix_package_locality" if patch_type == "replace_class_path" else "component_type_exact_surface_then_comment_similarity",
                }
            )
        updated = dict(row)
        updated["discovery_mode"] = "authoritative_local_surface"
        updated["source_index_mode"] = norm(surface_index.get("source_mode"))
        updated["repair_steps"] = steps
        updated["placement_kind"] = norm(spec.get("placement_kind")) or "same_component_dual_mismatch"
        rows.append(updated)
    return rows


def load_surface_index(path: str | Path) -> dict:
    return load_json(path)


def fixture_first_fix_detail(signature_text: str) -> dict:
    return {
        "executor_status": "FAILED",
        "attempts": [
            {
                "round": 1,
                "reason": "model check failed",
                "log_excerpt": signature_text,
                "diagnostic_ir": {
                    "dominant_stage_subtype": "stage_2_structural_balance_reference",
                    "error_subtype": "undefined_symbol",
                },
            }
        ],
    }
