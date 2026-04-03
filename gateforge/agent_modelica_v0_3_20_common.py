from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_v0_3_19_common import (
    DEFAULT_TASKSET_OUT_DIR as DEFAULT_V0319_TASKSET_OUT_DIR,
    build_source_specs as build_v0319_source_specs,
    error_signature_from_attempt,
    error_signature_from_text,
    norm,
    replacement_audit,
    run_synthetic_task_live,
)


SCHEMA_PREFIX = "agent_modelica_v0_3_20"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PATCH_CONTRACT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_20_patch_contract_current"
DEFAULT_TASKSET_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_20_taskset_current"
DEFAULT_FIRST_FIX_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_20_first_fix_results_current"
DEFAULT_FIRST_FIX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_20_first_fix_evidence_current"
DEFAULT_DUAL_RECHECK_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_20_dual_recheck_results_current"
DEFAULT_DUAL_RECHECK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_20_dual_recheck_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_20_closeout_current"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


AUTHORITATIVE_CLASS_PATH_CANDIDATES = {
    "Modelica.Blocks.Source.Sine": {
        "correct_symbol": "Modelica.Blocks.Sources.Sine",
        "candidate_class_paths": [
            "Modelica.Blocks.Sources.Sine",
        ],
    },
    "Modelica.Blocks.Source.Step": {
        "correct_symbol": "Modelica.Blocks.Sources.Step",
        "candidate_class_paths": [
            "Modelica.Blocks.Sources.Step",
        ],
    },
    "Modelica.Thermal.HeatTransfer.Components.FixedTemperature": {
        "correct_symbol": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
        "candidate_class_paths": [
            "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
        ],
    },
}

AUTHORITATIVE_PARAMETER_CANDIDATES = {
    ("Modelica.Blocks.Sources.Sine", "freqHz"): {
        "correct_symbol": "f",
        "candidate_parameter_names": ["f", "amplitude", "offset", "startTime", "phase"],
    },
    ("Modelica.Blocks.Sources.Sine", "amp"): {
        "correct_symbol": "amplitude",
        "candidate_parameter_names": ["amplitude", "f", "offset", "startTime", "phase"],
    },
    ("Modelica.Blocks.Sources.Step", "amplitude"): {
        "correct_symbol": "height",
        "candidate_parameter_names": ["height", "startTime", "offset"],
    },
    ("Modelica.Blocks.Sources.Step", "startT"): {
        "correct_symbol": "startTime",
        "candidate_parameter_names": ["startTime", "height", "offset"],
    },
    ("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "temperature"): {
        "correct_symbol": "T",
        "candidate_parameter_names": ["T"],
    },
}


def _source_row(source_id: str) -> dict:
    for row in build_v0319_source_specs():
        if norm(row.get("source_id")) == source_id:
            return row
    return {}


SINGLE_MISMATCH_SPECS = [
    {
        "task_id": "v0320_single_simple_sine_class_path",
        "source_id": "simple_sine_driven_mass",
        "complexity_tier": "simple",
        "patch_type": "replace_class_path",
        "component_type": "Modelica.Blocks.Sources.Sine",
        "wrong_symbol": "Modelica.Blocks.Source.Sine",
        "correct_symbol": "Modelica.Blocks.Sources.Sine",
        "candidate_key": "Modelica.Blocks.Source.Sine",
        "injection_replacements": [
            ("Modelica.Blocks.Sources.Sine", "Modelica.Blocks.Source.Sine"),
        ],
        "expected_first_error_signature_hint": "Class Modelica.Blocks.Source.Sine not found in scope",
    },
    {
        "task_id": "v0320_single_simple_sine_param_amp",
        "source_id": "simple_sine_driven_mass",
        "complexity_tier": "simple",
        "patch_type": "replace_parameter_name",
        "component_type": "Modelica.Blocks.Sources.Sine",
        "wrong_symbol": "amp",
        "correct_symbol": "amplitude",
        "candidate_key": ("Modelica.Blocks.Sources.Sine", "amp"),
        "injection_replacements": [
            ("amplitude = 5.0", "amp = 5.0"),
        ],
        "expected_first_error_signature_hint": "Modified element amp not found in class Sine",
    },
    {
        "task_id": "v0320_single_simple_thermal_class_path",
        "source_id": "simple_thermal_heated_mass",
        "complexity_tier": "simple",
        "patch_type": "replace_class_path",
        "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
        "wrong_symbol": "Modelica.Thermal.HeatTransfer.Components.FixedTemperature",
        "correct_symbol": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
        "candidate_key": "Modelica.Thermal.HeatTransfer.Components.FixedTemperature",
        "injection_replacements": [
            ("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "Modelica.Thermal.HeatTransfer.Components.FixedTemperature"),
        ],
        "expected_first_error_signature_hint": "Class Modelica.Thermal.HeatTransfer.Components.FixedTemperature not found in scope",
    },
    {
        "task_id": "v0320_single_medium_step_class_path",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "patch_type": "replace_class_path",
        "component_type": "Modelica.Blocks.Sources.Step",
        "wrong_symbol": "Modelica.Blocks.Source.Step",
        "correct_symbol": "Modelica.Blocks.Sources.Step",
        "candidate_key": "Modelica.Blocks.Source.Step",
        "injection_replacements": [
            ("Modelica.Blocks.Sources.Step", "Modelica.Blocks.Source.Step"),
        ],
        "expected_first_error_signature_hint": "Class Modelica.Blocks.Source.Step not found in scope",
    },
    {
        "task_id": "v0320_single_medium_step_param_amp",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "patch_type": "replace_parameter_name",
        "component_type": "Modelica.Blocks.Sources.Step",
        "wrong_symbol": "amplitude",
        "correct_symbol": "height",
        "candidate_key": ("Modelica.Blocks.Sources.Step", "amplitude"),
        "injection_replacements": [
            ("height = 1.0", "amplitude = 1.0"),
        ],
        "expected_first_error_signature_hint": "Modified element amplitude not found in class Step",
    },
    {
        "task_id": "v0320_single_medium_thermal_class_path",
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "patch_type": "replace_class_path",
        "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
        "wrong_symbol": "Modelica.Thermal.HeatTransfer.Components.FixedTemperature",
        "correct_symbol": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
        "candidate_key": "Modelica.Thermal.HeatTransfer.Components.FixedTemperature",
        "injection_replacements": [
            ("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "Modelica.Thermal.HeatTransfer.Components.FixedTemperature"),
        ],
        "expected_first_error_signature_hint": "Class Modelica.Thermal.HeatTransfer.Components.FixedTemperature not found in scope",
    },
]


DUAL_RECHECK_SPECS = [
    {
        "task_id": "v0320_dual_simple_sine_class_param",
        "source_id": "simple_sine_driven_mass",
        "complexity_tier": "simple",
        "repair_steps": [
            {
                "patch_type": "replace_class_path",
                "component_type": "Modelica.Blocks.Sources.Sine",
                "wrong_symbol": "Modelica.Blocks.Source.Sine",
                "correct_symbol": "Modelica.Blocks.Sources.Sine",
                "candidate_key": "Modelica.Blocks.Source.Sine",
            },
            {
                "patch_type": "replace_parameter_name",
                "component_type": "Modelica.Blocks.Sources.Sine",
                "wrong_symbol": "freqHz",
                "correct_symbol": "f",
                "candidate_key": ("Modelica.Blocks.Sources.Sine", "freqHz"),
            },
        ],
        "injection_replacements": [
            ("Modelica.Blocks.Sources.Sine", "Modelica.Blocks.Source.Sine"),
            ("f = 0.5", "freqHz = 0.5"),
        ],
    },
    {
        "task_id": "v0320_dual_simple_sine_param_param",
        "source_id": "simple_sine_driven_mass",
        "complexity_tier": "simple",
        "repair_steps": [
            {
                "patch_type": "replace_parameter_name",
                "component_type": "Modelica.Blocks.Sources.Sine",
                "wrong_symbol": "amp",
                "correct_symbol": "amplitude",
                "candidate_key": ("Modelica.Blocks.Sources.Sine", "amp"),
            },
            {
                "patch_type": "replace_parameter_name",
                "component_type": "Modelica.Blocks.Sources.Sine",
                "wrong_symbol": "freqHz",
                "correct_symbol": "f",
                "candidate_key": ("Modelica.Blocks.Sources.Sine", "freqHz"),
            },
        ],
        "injection_replacements": [
            ("amplitude = 5.0", "amp = 5.0"),
            ("f = 0.5", "freqHz = 0.5"),
        ],
    },
    {
        "task_id": "v0320_dual_simple_thermal_class_param",
        "source_id": "simple_thermal_heated_mass",
        "complexity_tier": "simple",
        "repair_steps": [
            {
                "patch_type": "replace_class_path",
                "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
                "wrong_symbol": "Modelica.Thermal.HeatTransfer.Components.FixedTemperature",
                "correct_symbol": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
                "candidate_key": "Modelica.Thermal.HeatTransfer.Components.FixedTemperature",
            },
            {
                "patch_type": "replace_parameter_name",
                "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
                "wrong_symbol": "temperature",
                "correct_symbol": "T",
                "candidate_key": ("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "temperature"),
            },
        ],
        "injection_replacements": [
            ("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "Modelica.Thermal.HeatTransfer.Components.FixedTemperature"),
            ("T = 293.15", "temperature = 293.15"),
        ],
    },
    {
        "task_id": "v0320_dual_medium_step_class_param",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "repair_steps": [
            {
                "patch_type": "replace_class_path",
                "component_type": "Modelica.Blocks.Sources.Step",
                "wrong_symbol": "Modelica.Blocks.Source.Step",
                "correct_symbol": "Modelica.Blocks.Sources.Step",
                "candidate_key": "Modelica.Blocks.Source.Step",
            },
            {
                "patch_type": "replace_parameter_name",
                "component_type": "Modelica.Blocks.Sources.Step",
                "wrong_symbol": "startT",
                "correct_symbol": "startTime",
                "candidate_key": ("Modelica.Blocks.Sources.Step", "startT"),
            },
        ],
        "injection_replacements": [
            ("Modelica.Blocks.Sources.Step", "Modelica.Blocks.Source.Step"),
            ("startTime = 0.5", "startT = 0.5"),
        ],
    },
    {
        "task_id": "v0320_dual_medium_step_param_param",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "repair_steps": [
            {
                "patch_type": "replace_parameter_name",
                "component_type": "Modelica.Blocks.Sources.Step",
                "wrong_symbol": "amplitude",
                "correct_symbol": "height",
                "candidate_key": ("Modelica.Blocks.Sources.Step", "amplitude"),
            },
            {
                "patch_type": "replace_parameter_name",
                "component_type": "Modelica.Blocks.Sources.Step",
                "wrong_symbol": "startT",
                "correct_symbol": "startTime",
                "candidate_key": ("Modelica.Blocks.Sources.Step", "startT"),
            },
        ],
        "injection_replacements": [
            ("height = 1.0", "amplitude = 1.0"),
            ("startTime = 0.5", "startT = 0.5"),
        ],
    },
    {
        "task_id": "v0320_dual_medium_thermal_class_param",
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "repair_steps": [
            {
                "patch_type": "replace_class_path",
                "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
                "wrong_symbol": "Modelica.Thermal.HeatTransfer.Components.FixedTemperature",
                "correct_symbol": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
                "candidate_key": "Modelica.Thermal.HeatTransfer.Components.FixedTemperature",
            },
            {
                "patch_type": "replace_parameter_name",
                "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
                "wrong_symbol": "temperature",
                "correct_symbol": "T",
                "candidate_key": ("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "temperature"),
            },
        ],
        "injection_replacements": [
            ("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "Modelica.Thermal.HeatTransfer.Components.FixedTemperature"),
            ("T = 293.15", "temperature = 293.15"),
        ],
    },
]


def authoritative_candidates_for(patch_type: str, candidate_key: object) -> list[str]:
    lookup_key = _candidate_lookup_key(candidate_key)
    if patch_type == "replace_class_path":
        row = AUTHORITATIVE_CLASS_PATH_CANDIDATES.get(norm(lookup_key)) or {}
        return list(row.get("candidate_class_paths") or [])
    row = AUTHORITATIVE_PARAMETER_CANDIDATES.get(lookup_key) or {}
    return list(row.get("candidate_parameter_names") or [])


def authoritative_correct_symbol_for(patch_type: str, candidate_key: object) -> str:
    lookup_key = _candidate_lookup_key(candidate_key)
    if patch_type == "replace_class_path":
        row = AUTHORITATIVE_CLASS_PATH_CANDIDATES.get(norm(lookup_key)) or {}
        return norm(row.get("correct_symbol"))
    row = AUTHORITATIVE_PARAMETER_CANDIDATES.get(lookup_key) or {}
    return norm(row.get("correct_symbol"))


def _candidate_lookup_key(candidate_key: object) -> object:
    if isinstance(candidate_key, list):
        return tuple(norm(item) for item in candidate_key)
    if isinstance(candidate_key, tuple):
        return tuple(norm(item) for item in candidate_key)
    return norm(candidate_key)


def build_single_task_rows() -> list[dict]:
    rows: list[dict] = []
    for spec in SINGLE_MISMATCH_SPECS:
        source = _source_row(norm(spec.get("source_id")))
        mutated_model_text, audit = replacement_audit(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        rows.append(
            {
                "schema_version": f"{SCHEMA_PREFIX}_single_task",
                "generated_at_utc": now_utc(),
                "task_id": norm(spec.get("task_id")),
                "complexity_tier": norm(spec.get("complexity_tier")),
                "source_id": norm(spec.get("source_id")),
                "model_name": norm(source.get("model_name")),
                "source_model_text": norm(source.get("source_model_text")),
                "mutated_model_text": mutated_model_text,
                "declared_failure_type": "model_check_error",
                "expected_stage": "check",
                "patch_type": norm(spec.get("patch_type")),
                "component_type": norm(spec.get("component_type")),
                "wrong_symbol": norm(spec.get("wrong_symbol")),
                "correct_symbol": norm(spec.get("correct_symbol")),
                "candidate_key_repr": repr(spec.get("candidate_key")),
                "candidate_key": spec.get("candidate_key"),
                "candidate_symbols": authoritative_candidates_for(norm(spec.get("patch_type")), spec.get("candidate_key")),
                "expected_first_error_signature_hint": norm(spec.get("expected_first_error_signature_hint")),
                "mutation_audit": audit,
            }
        )
    return rows


def build_dual_task_rows() -> list[dict]:
    rows: list[dict] = []
    for spec in DUAL_RECHECK_SPECS:
        source = _source_row(norm(spec.get("source_id")))
        mutated_model_text, audit = replacement_audit(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        repair_steps = []
        for step in spec.get("repair_steps") or []:
            repair_steps.append(
                {
                    "patch_type": norm(step.get("patch_type")),
                    "component_type": norm(step.get("component_type")),
                    "wrong_symbol": norm(step.get("wrong_symbol")),
                    "correct_symbol": norm(step.get("correct_symbol")),
                    "candidate_key_repr": repr(step.get("candidate_key")),
                    "candidate_symbols": authoritative_candidates_for(norm(step.get("patch_type")), step.get("candidate_key")),
                }
            )
        rows.append(
            {
                "schema_version": f"{SCHEMA_PREFIX}_dual_task",
                "generated_at_utc": now_utc(),
                "task_id": norm(spec.get("task_id")),
                "complexity_tier": norm(spec.get("complexity_tier")),
                "source_id": norm(spec.get("source_id")),
                "model_name": norm(source.get("model_name")),
                "source_model_text": norm(source.get("source_model_text")),
                "mutated_model_text": mutated_model_text,
                "declared_failure_type": "model_check_error",
                "expected_stage": "check",
                "repair_steps": repair_steps,
                "mutation_audit": audit,
            }
        )
    return rows


def apply_constrained_first_fix(*, current_text: str, patch_type: str, wrong_symbol: str, candidate_key: object) -> tuple[str, dict]:
    correct_symbol = authoritative_correct_symbol_for(patch_type, candidate_key)
    candidates = authoritative_candidates_for(patch_type, candidate_key)
    if not correct_symbol or correct_symbol not in candidates:
        return current_text, {
            "applied": False,
            "reason": "authoritative_candidate_missing",
            "selected_candidate": correct_symbol,
            "candidate_symbols": candidates,
        }
    current = str(current_text or "")
    if patch_type == "replace_parameter_name":
        pattern = re.compile(rf"\b{re.escape(wrong_symbol)}\b(?=\s*=)")
        if not pattern.search(current):
            return current_text, {
                "applied": False,
                "reason": "wrong_symbol_not_found_in_parameter_binding",
                "selected_candidate": correct_symbol,
                "candidate_symbols": candidates,
            }
        patched = pattern.sub(correct_symbol, current, count=1)
    else:
        if wrong_symbol not in current:
            return current_text, {
                "applied": False,
                "reason": "wrong_symbol_not_found_in_text",
                "selected_candidate": correct_symbol,
                "candidate_symbols": candidates,
            }
        patched = current.replace(wrong_symbol, correct_symbol, 1)
    return patched, {
        "applied": patched != current,
        "reason": "applied_minimal_patch" if patched != current else "text_unchanged_after_patch",
        "selected_candidate": correct_symbol,
        "candidate_symbols": candidates,
        "wrong_symbol": wrong_symbol,
        "correct_symbol": correct_symbol,
    }


def first_attempt_signature(detail: dict) -> tuple[str, dict]:
    attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
    if attempts and isinstance(attempts[0], dict):
        attempt = attempts[0]
        diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
        return (
            error_signature_from_attempt(attempt),
            {
                "dominant_stage_subtype": norm(diagnostic.get("dominant_stage_subtype") or detail.get("dominant_stage_subtype")),
                "error_subtype": norm(diagnostic.get("error_subtype")),
                "reason": norm(attempt.get("reason") or diagnostic.get("reason")),
            },
        )
    return "", {
        "dominant_stage_subtype": norm(detail.get("dominant_stage_subtype")),
        "error_subtype": "",
        "reason": "",
    }


def rerun_once(*, task_id: str, model_text: str, result_dir: str | Path, evaluation_label: str, timeout_sec: int = 600) -> dict:
    pseudo_task = {
        "task_id": task_id,
        "source_model_text": model_text,
        "mutated_model_text": model_text,
        "declared_failure_type": "model_check_error",
        "expected_stage": "check",
    }
    return run_synthetic_task_live(
        task=pseudo_task,
        result_dir=result_dir,
        evaluation_label=evaluation_label,
        max_rounds=1,
        timeout_sec=timeout_sec,
    )
