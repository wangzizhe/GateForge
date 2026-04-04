from __future__ import annotations

import re
from pathlib import Path

from .agent_modelica_v0_3_19_common import DOCKER_IMAGE
from .agent_modelica_v0_3_20_common import (
    first_attempt_signature,
    load_json,
    norm,
    rerun_once,
    replacement_audit,
    run_synthetic_task_live,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_21_common import now_utc
from .agent_modelica_v0_3_23_common import (
    DUAL_RECHECK_SPECS as V0323_DUAL_RECHECK_SPECS,
    SINGLE_MISMATCH_SPECS as V0323_SINGLE_MISMATCH_SPECS,
    TARGET_ERROR_SUBTYPE,
    TARGET_STAGE_SUBTYPE,
    build_v0323_source_specs,
    classify_dry_run_output,
    dry_run_dual_task,
    dry_run_single_task,
    fixture_dry_run_result,
)


SCHEMA_PREFIX = "agent_modelica_v0_3_24"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SURFACE_INDEX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_24_surface_index_current"
DEFAULT_TASKSET_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_24_taskset_current"
DEFAULT_PATCH_CONTRACT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_24_patch_contract_current"
DEFAULT_FIRST_FIX_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_24_first_fix_results_current"
DEFAULT_FIRST_FIX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_24_first_fix_evidence_current"
DEFAULT_DUAL_RECHECK_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_24_dual_recheck_results_current"
DEFAULT_DUAL_RECHECK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_24_dual_recheck_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_24_closeout_current"


def _clone_spec_with_v0324_id(spec: dict) -> dict:
    updated = dict(spec)
    updated["task_id"] = norm(spec.get("task_id")).replace("v0323_", "v0324_", 1)
    return updated


ADDITIONAL_SINGLE_MISMATCH_SPECS = [
    {
        "task_id": "v0324_single_medium_actuator_inputsignal",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "patch_type": "replace_local_port_symbol",
        "wrong_symbol": "actuator.inputSignal",
        "correct_symbol": "actuator.u",
        "candidate_key": "actuator.inputSignal",
        "injection_replacements": [("connect(controller.y, actuator.u);", "connect(controller.y, actuator.inputSignal);")],
    },
    {
        "task_id": "v0324_single_medium_actuator_out",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "patch_type": "replace_local_port_symbol",
        "wrong_symbol": "actuator.out",
        "correct_symbol": "actuator.y",
        "candidate_key": "actuator.out",
        "injection_replacements": [("connect(actuator.y, force.f);", "connect(actuator.out, force.f);")],
    },
]


ADDITIONAL_DUAL_RECHECK_SPECS = [
    {
        "task_id": "v0324_dual_medium_actuator_component",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {
                "patch_type": "replace_local_port_symbol",
                "wrong_symbol": "actuator.inputSignal",
                "correct_symbol": "actuator.u",
                "candidate_key": "actuator.inputSignal",
            },
            {
                "patch_type": "replace_local_port_symbol",
                "wrong_symbol": "actuator.out",
                "correct_symbol": "actuator.y",
                "candidate_key": "actuator.out",
            },
        ],
        "injection_replacements": [
            ("connect(controller.y, actuator.u);", "connect(controller.y, actuator.inputSignal);"),
            ("connect(actuator.y, force.f);", "connect(actuator.out, force.f);"),
        ],
    }
]


SINGLE_MISMATCH_SPECS = [_clone_spec_with_v0324_id(spec) for spec in V0323_SINGLE_MISMATCH_SPECS] + [
    dict(spec) for spec in ADDITIONAL_SINGLE_MISMATCH_SPECS
]

DUAL_RECHECK_SPECS = [_clone_spec_with_v0324_id(spec) for spec in V0323_DUAL_RECHECK_SPECS] + [
    dict(spec) for spec in ADDITIONAL_DUAL_RECHECK_SPECS
]


SIGNAL_ROLE_PRIOR = {
    "outsig": ["y"],
    "out": ["y"],
    "inputsignal": ["u"],
    "input1": ["u1", "u"],
    "input2": ["u2", "u"],
    "qin": ["Q_flow"],
}

CONNECTOR_SIDE_PRIOR = {
    "portleft": ["port_a"],
    "portright": ["port_b"],
    "pospin": ["p"],
    "negpin": ["n"],
}

TOKEN_EXPANSIONS = {
    "outsig": ["out", "signal", "y"],
    "out": ["output", "y"],
    "inputsignal": ["input", "signal", "u"],
    "input1": ["input", "u1", "u", "1"],
    "input2": ["input", "u2", "u", "2"],
    "qin": ["q", "flow", "q_flow", "heat"],
    "qflow": ["q_flow", "q", "flow", "heat"],
    "portleft": ["port", "left", "a", "port_a"],
    "portright": ["port", "right", "b", "port_b"],
    "pospin": ["pos", "positive", "p", "pin"],
    "negpin": ["neg", "negative", "n", "pin"],
    "u": ["input"],
    "u1": ["input", "u", "1"],
    "u2": ["input", "u", "2"],
    "y": ["output", "signal", "out"],
    "p": ["positive", "pos"],
    "n": ["negative", "neg"],
    "porta": ["port", "a", "left", "port_a"],
    "portb": ["port", "b", "right", "port_b"],
}


def build_v0324_source_specs() -> list[dict]:
    return [dict(row) for row in build_v0323_source_specs()]


def _source_row(source_id: str) -> dict:
    for row in build_v0324_source_specs():
        if norm(row.get("source_id")) == norm(source_id):
            return row
    return {}


def _extract_local_surface_symbols(source_model_text: str, component_name: str) -> list[str]:
    prefix = re.escape(norm(component_name))
    pattern = re.compile(rf"\b{prefix}\.([A-Za-z_][A-Za-z0-9_]*)\b")
    seen: list[str] = []
    for match in pattern.finditer(norm(source_model_text)):
        symbol = f"{norm(component_name)}.{norm(match.group(1))}"
        if symbol and symbol not in seen:
            seen.append(symbol)
    return seen


def _component_name(symbol: str) -> str:
    value = norm(symbol)
    return value.split(".", 1)[0] if "." in value else value


def _member_name(symbol: str) -> str:
    value = norm(symbol)
    return value.split(".", 1)[1] if "." in value else value


def _normalize_token(token: str) -> str:
    value = norm(token)
    if not value:
        return ""
    return re.sub(r"[^A-Za-z0-9]+", "", value).lower()


def _split_tokens(text: str) -> list[str]:
    raw = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", norm(text))
    chunks = [chunk for chunk in re.split(r"[^A-Za-z0-9]+", raw) if chunk]
    tokens: list[str] = []
    for chunk in chunks:
        base = _normalize_token(chunk)
        if not base:
            continue
        tokens.append(base)
        for expanded in TOKEN_EXPANSIONS.get(base, []):
            normalized = _normalize_token(expanded)
            if normalized:
                tokens.append(normalized)
    return tokens


def _shared_count(a: list[str], b: list[str]) -> int:
    return len(set(a) & set(b))


def build_surface_index_payload(*, use_fixture_only: bool = False) -> dict:
    records: dict[str, dict] = {}
    export_failures: list[dict] = []
    source_specs = build_v0324_source_specs()
    source_by_id = {norm(row.get("source_id")): row for row in source_specs}
    all_specs = list(SINGLE_MISMATCH_SPECS)
    for spec in DUAL_RECHECK_SPECS:
        for step in spec.get("repair_steps") or []:
            all_specs.append(
                {
                    "source_id": spec.get("source_id"),
                    "complexity_tier": spec.get("complexity_tier"),
                    "component_family": spec.get("component_family"),
                    "patch_type": step.get("patch_type"),
                    "wrong_symbol": step.get("wrong_symbol"),
                    "correct_symbol": step.get("correct_symbol"),
                    "candidate_key": step.get("candidate_key"),
                }
            )
    seen_keys: set[str] = set()
    for spec in all_specs:
        key = norm(spec.get("candidate_key"))
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        source = source_by_id.get(norm(spec.get("source_id"))) or {}
        component_name = _component_name(key)
        candidate_symbols = _extract_local_surface_symbols(norm(source.get("source_model_text")), component_name)
        if not candidate_symbols:
            export_failures.append(
                {
                    "candidate_key": key,
                    "source_id": norm(spec.get("source_id")),
                    "component_family": norm(spec.get("component_family")),
                    "reason": "empty_local_surface_for_component",
                }
            )
            continue
        records[key] = {
            "candidate_key": key,
            "source_id": norm(spec.get("source_id")),
            "complexity_tier": norm(spec.get("complexity_tier")),
            "component_family": norm(spec.get("component_family")),
            "patch_type": norm(spec.get("patch_type")),
            "component_name": component_name,
            "canonical_symbol": norm(spec.get("correct_symbol")),
            "candidate_symbols": candidate_symbols,
        }
    success_count = len(records)
    total_count = len(seen_keys)
    return {
        "source_mode": "source_model_local_surface",
        "omc_backend": "openmodelica_docker",
        "docker_image": DOCKER_IMAGE,
        "modelica_version": "inherited_from_current_docker_runtime",
        "use_fixture_only": bool(use_fixture_only),
        "surface_records": records,
        "surface_export_total_count": total_count,
        "surface_export_success_count": success_count,
        "surface_export_success_rate_pct": round(100.0 * success_count / float(total_count), 1) if total_count else 0.0,
        "fixture_fallback_count": 0,
        "fixture_fallback_rate_pct": 0.0,
        "export_failures": export_failures,
    }


def local_surface_record_for(surface_index: dict, candidate_key: str) -> dict:
    records = surface_index.get("surface_records") if isinstance(surface_index.get("surface_records"), dict) else {}
    record = records.get(norm(candidate_key))
    return dict(record) if isinstance(record, dict) else {}


def candidate_symbols_for(surface_index: dict, candidate_key: str) -> list[str]:
    record = local_surface_record_for(surface_index, candidate_key)
    rows = record.get("candidate_symbols")
    return [norm(item) for item in rows if norm(item)] if isinstance(rows, list) else []


def _rank_signal_port_candidates(*, wrong_symbol: str, candidates: list[str]) -> list[dict]:
    wrong_leaf = _member_name(wrong_symbol)
    wrong_token_key = _normalize_token(wrong_leaf)
    preferred = SIGNAL_ROLE_PRIOR.get(wrong_token_key, [])
    wrong_tokens = _split_tokens(wrong_leaf)
    rows: list[dict] = []
    for idx, candidate in enumerate(candidates):
        candidate_leaf = _member_name(candidate)
        candidate_key = norm(candidate_leaf)
        candidate_tokens = _split_tokens(candidate_leaf)
        score = 20 * _shared_count(wrong_tokens, candidate_tokens)
        if candidate_key in preferred:
            score += 100
        if any(candidate_key.startswith(item) for item in preferred):
            score += 20
        rows.append(
            {
                "candidate": candidate,
                "score": score,
                "rank_features": {
                    "signal_role_prior_match": candidate_key in preferred,
                    "token_overlap": _shared_count(wrong_tokens, candidate_tokens),
                    "input_order": idx,
                },
            }
        )
    rows.sort(key=lambda row: (-int(row.get("score") or 0), int((row.get("rank_features") or {}).get("input_order") or 0), norm(row.get("candidate"))))
    return rows


def _rank_connector_side_candidates(*, wrong_symbol: str, candidates: list[str]) -> list[dict]:
    wrong_leaf = _member_name(wrong_symbol)
    wrong_token_key = _normalize_token(wrong_leaf)
    preferred = CONNECTOR_SIDE_PRIOR.get(wrong_token_key, [])
    wrong_tokens = _split_tokens(wrong_leaf)
    rows: list[dict] = []
    for idx, candidate in enumerate(candidates):
        candidate_leaf = _member_name(candidate)
        candidate_key = norm(candidate_leaf)
        candidate_tokens = _split_tokens(candidate_leaf)
        score = 20 * _shared_count(wrong_tokens, candidate_tokens)
        if candidate_key in preferred:
            score += 100
        if any(candidate_key.startswith(item) for item in preferred):
            score += 20
        rows.append(
            {
                "candidate": candidate,
                "score": score,
                "rank_features": {
                    "connector_side_prior_match": candidate_key in preferred,
                    "token_overlap": _shared_count(wrong_tokens, candidate_tokens),
                    "input_order": idx,
                },
            }
        )
    rows.sort(key=lambda row: (-int(row.get("score") or 0), int((row.get("rank_features") or {}).get("input_order") or 0), norm(row.get("candidate"))))
    return rows


def rank_interface_candidates(*, component_family: str, wrong_symbol: str, candidates: list[str]) -> list[dict]:
    if norm(component_family) == "local_connector_side_alignment":
        return _rank_connector_side_candidates(wrong_symbol=wrong_symbol, candidates=candidates)
    return _rank_signal_port_candidates(wrong_symbol=wrong_symbol, candidates=candidates)


def apply_interface_discovery_first_fix(
    *,
    current_text: str,
    patch_type: str,
    wrong_symbol: str,
    canonical_symbol: str,
    component_family: str,
    candidate_symbols: list[str] | None = None,
) -> tuple[str, dict]:
    current = str(current_text or "")
    candidates = [norm(item) for item in (candidate_symbols or []) if norm(item)]
    ranked = rank_interface_candidates(component_family=component_family, wrong_symbol=wrong_symbol, candidates=candidates)
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
        "reason": "applied_interface_discovery_patch" if patched != current else "text_unchanged_after_patch",
        "selected_candidate": selected,
        "candidate_symbols": candidates,
        "candidate_contains_canonical": canonical_symbol in candidates,
        "candidate_top1_is_canonical": selected == canonical_symbol,
        "ranked_candidates": ranked,
        "patch_type": norm(patch_type),
        "wrong_symbol": norm(wrong_symbol),
    }


def build_single_task_rows(surface_index: dict) -> list[dict]:
    rows: list[dict] = []
    for spec in SINGLE_MISMATCH_SPECS:
        source = _source_row(spec.get("source_id"))
        mutated_model_text, audit = replacement_audit(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        candidate_symbols = candidate_symbols_for(surface_index, norm(spec.get("candidate_key")))
        rows.append(
            {
                "schema_version": f"{SCHEMA_PREFIX}_single_task",
                "generated_at_utc": now_utc(),
                "task_id": norm(spec.get("task_id")),
                "complexity_tier": norm(spec.get("complexity_tier")),
                "source_id": norm(spec.get("source_id")),
                "component_family": norm(spec.get("component_family")),
                "model_name": norm(source.get("model_name")),
                "source_model_text": norm(source.get("source_model_text")),
                "mutated_model_text": mutated_model_text,
                "declared_failure_type": "model_check_error",
                "expected_stage": "check",
                "patch_type": norm(spec.get("patch_type")),
                "wrong_symbol": norm(spec.get("wrong_symbol")),
                "correct_symbol": norm(spec.get("correct_symbol")),
                "candidate_key": norm(spec.get("candidate_key")),
                "candidate_symbols": candidate_symbols,
                "mutation_audit": audit,
                "discovery_mode": "authoritative_local_interface_surface",
            }
        )
    return rows


def build_dual_task_rows(surface_index: dict) -> list[dict]:
    rows: list[dict] = []
    for spec in DUAL_RECHECK_SPECS:
        source = _source_row(spec.get("source_id"))
        mutated_model_text, audit = replacement_audit(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        repair_steps = []
        for step in spec.get("repair_steps") or []:
            repair_steps.append(
                {
                    "patch_type": norm(step.get("patch_type")),
                    "wrong_symbol": norm(step.get("wrong_symbol")),
                    "correct_symbol": norm(step.get("correct_symbol")),
                    "candidate_key": norm(step.get("candidate_key")),
                    "candidate_symbols": candidate_symbols_for(surface_index, norm(step.get("candidate_key"))),
                }
            )
        rows.append(
            {
                "schema_version": f"{SCHEMA_PREFIX}_dual_task",
                "generated_at_utc": now_utc(),
                "task_id": norm(spec.get("task_id")),
                "complexity_tier": norm(spec.get("complexity_tier")),
                "source_id": norm(spec.get("source_id")),
                "component_family": norm(spec.get("component_family")),
                "placement_kind": norm(spec.get("placement_kind")),
                "model_name": norm(source.get("model_name")),
                "source_model_text": norm(source.get("source_model_text")),
                "mutated_model_text": mutated_model_text,
                "repair_steps": repair_steps,
                "mutation_audit": audit,
                "discovery_mode": "authoritative_local_interface_surface",
            }
        )
    return rows


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DUAL_RECHECK_OUT_DIR",
    "DEFAULT_DUAL_RECHECK_RESULTS_DIR",
    "DEFAULT_FIRST_FIX_OUT_DIR",
    "DEFAULT_FIRST_FIX_RESULTS_DIR",
    "DEFAULT_PATCH_CONTRACT_OUT_DIR",
    "DEFAULT_SURFACE_INDEX_OUT_DIR",
    "DEFAULT_TASKSET_OUT_DIR",
    "DOCKER_IMAGE",
    "DUAL_RECHECK_SPECS",
    "SCHEMA_PREFIX",
    "SINGLE_MISMATCH_SPECS",
    "TARGET_ERROR_SUBTYPE",
    "TARGET_STAGE_SUBTYPE",
    "apply_interface_discovery_first_fix",
    "build_dual_task_rows",
    "build_single_task_rows",
    "build_surface_index_payload",
    "build_v0324_source_specs",
    "candidate_symbols_for",
    "classify_dry_run_output",
    "dry_run_dual_task",
    "dry_run_single_task",
    "fixture_dry_run_result",
    "first_attempt_signature",
    "load_json",
    "local_surface_record_for",
    "norm",
    "now_utc",
    "rerun_once",
    "run_synthetic_task_live",
    "write_json",
    "write_text",
]
