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
    TARGET_ERROR_SUBTYPE,
    TARGET_STAGE_SUBTYPE,
    classify_dry_run_output,
    dry_run_dual_task,
    dry_run_single_task,
    fixture_dry_run_result,
)
from .agent_modelica_v0_3_25_common import build_v0325_source_specs


SCHEMA_PREFIX = "agent_modelica_v0_3_27"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MANIFEST_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_27_coverage_manifest_current"
DEFAULT_SURFACE_INDEX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_27_surface_index_current"
DEFAULT_SURFACE_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_27_surface_export_audit_current"
DEFAULT_TASKSET_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_27_taskset_current"
DEFAULT_TASKSET_PRECHECK_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_27_taskset_precheck_results_current"
DEFAULT_PATCH_CONTRACT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_27_patch_contract_current"
DEFAULT_FIRST_FIX_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_27_first_fix_results_current"
DEFAULT_FIRST_FIX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_27_first_fix_evidence_current"
DEFAULT_DUAL_RECHECK_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_27_dual_recheck_results_current"
DEFAULT_DUAL_RECHECK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_27_dual_recheck_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_27_closeout_current"


SIGNAL_ROLE_PRIOR = {
    "outsig": ["y"],
    "out": ["y"],
    "inputsignal": ["u"],
    "input1": ["u1", "u"],
    "input2": ["u2", "u"],
    "qin": ["Q_flow"],
    "porthot": ["port"],
}

CONNECTOR_SIDE_PRIOR = {
    "portleft": ["port_a"],
    "portright": ["port_b"],
    "pospin": ["p"],
    "negpin": ["n"],
    "leftflange": ["flange_a"],
    "rightflange": ["flange_b"],
}

TOKEN_EXPANSIONS = {
    "outsig": ["out", "signal", "y"],
    "out": ["output", "y"],
    "inputsignal": ["input", "signal", "u"],
    "input1": ["input", "u1", "u", "1"],
    "input2": ["input", "u2", "u", "2"],
    "qin": ["q", "flow", "q_flow", "heat"],
    "qflow": ["q_flow", "q", "flow", "heat"],
    "porthot": ["port", "hot"],
    "portleft": ["port", "left", "a", "port_a"],
    "portright": ["port", "right", "b", "port_b"],
    "pospin": ["pos", "positive", "p", "pin"],
    "negpin": ["neg", "negative", "n", "pin"],
    "leftflange": ["left", "flange", "a", "flange_a"],
    "rightflange": ["right", "flange", "b", "flange_b"],
    "u": ["input"],
    "u1": ["input", "u", "1"],
    "u2": ["input", "u", "2"],
    "y": ["output", "signal", "out"],
    "p": ["positive", "pos"],
    "n": ["negative", "neg"],
    "porta": ["port", "a", "left", "port_a"],
    "portb": ["port", "b", "right", "port_b"],
    "flangea": ["flange", "a", "left", "flange_a"],
    "flangeb": ["flange", "b", "right", "flange_b"],
}


COMPONENT_TYPE_LOCAL_SURFACE = {
    "Modelica.Blocks.Math.Feedback": ["u1", "u2", "y"],
    "Modelica.Blocks.Math.Gain": ["u", "y"],
    "Modelica.Blocks.Continuous.PI": ["u", "y"],
    "Modelica.Blocks.Sources.Step": ["y"],
    "Modelica.Blocks.Sources.Sine": ["y"],
    "Modelica.Blocks.Sources.Constant": ["y"],
    "Modelica.Electrical.Analog.Sources.SineVoltage": ["p", "n"],
    "Modelica.Electrical.Analog.Basic.Resistor": ["p", "n"],
    "Modelica.Electrical.Analog.Basic.Inductor": ["p", "n"],
    "Modelica.Electrical.Analog.Basic.Ground": ["p"],
    "Modelica.Mechanics.Translational.Components.Spring": ["flange_a", "flange_b"],
    "Modelica.Mechanics.Translational.Components.Damper": ["flange_a", "flange_b"],
    "Modelica.Mechanics.Translational.Components.Fixed": ["flange"],
    "Modelica.Mechanics.Translational.Sources.Force": ["f", "flange"],
    "Modelica.Thermal.HeatTransfer.Components.HeatCapacitor": ["port"],
    "Modelica.Thermal.HeatTransfer.Components.ThermalResistor": ["port_a", "port_b"],
    "Modelica.Thermal.HeatTransfer.Sources.PrescribedHeatFlow": ["Q_flow", "port"],
    "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature": ["port"],
}


def build_v0327_source_specs() -> list[dict]:
    return [dict(row) for row in build_v0325_source_specs()]


def _source_row(source_id: str) -> dict:
    for row in build_v0327_source_specs():
        if norm(row.get("source_id")) == norm(source_id):
            return row
    return {}


DUAL_RECHECK_SPECS = [
    {
        "task_id": "v0327_dual_simple_qflow_heater_neighbor",
        "source_id": "simple_thermal_heated_mass",
        "complexity_tier": "simple",
        "component_family": "local_signal_port_alignment",
        "placement_kind": "neighbor_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "Q_flow.outSig", "correct_symbol": "Q_flow.y", "candidate_key": "Q_flow.outSig"},
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "heater.qIn", "correct_symbol": "heater.Q_flow", "candidate_key": "heater.qIn"},
        ],
        "single_step_injection_replacements": [
            [("connect(Q_flow.y, heater.Q_flow);", "connect(Q_flow.outSig, heater.Q_flow);")],
            [("connect(Q_flow.y, heater.Q_flow);", "connect(Q_flow.y, heater.qIn);")],
        ],
        "injection_replacements": [("connect(Q_flow.y, heater.Q_flow);", "connect(Q_flow.outSig, heater.qIn);")],
    },
    {
        "task_id": "v0327_dual_medium_reference_feedback_neighbor",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "placement_kind": "neighbor_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "reference.outSig", "correct_symbol": "reference.y", "candidate_key": "reference.outSig"},
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "feedback.input1", "correct_symbol": "feedback.u1", "candidate_key": "feedback.input1"},
        ],
        "single_step_injection_replacements": [
            [("connect(reference.y, feedback.u1);", "connect(reference.outSig, feedback.u1);")],
            [("connect(reference.y, feedback.u1);", "connect(reference.y, feedback.input1);")],
        ],
        "injection_replacements": [("connect(reference.y, feedback.u1);", "connect(reference.outSig, feedback.input1);")],
    },
    {
        "task_id": "v0327_dual_medium_feedback_controller_neighbor",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "placement_kind": "neighbor_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "feedback.outSig", "correct_symbol": "feedback.y", "candidate_key": "feedback.outSig"},
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "controller.inputSignal", "correct_symbol": "controller.u", "candidate_key": "controller.inputSignal"},
        ],
        "single_step_injection_replacements": [
            [("connect(feedback.y, controller.u);", "connect(feedback.outSig, controller.u);")],
            [("connect(feedback.y, controller.u);", "connect(feedback.y, controller.inputSignal);")],
        ],
        "injection_replacements": [("connect(feedback.y, controller.u);", "connect(feedback.outSig, controller.inputSignal);")],
    },
    {
        "task_id": "v0327_dual_medium_controller_actuator_neighbor",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "placement_kind": "neighbor_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "controller.out", "correct_symbol": "controller.y", "candidate_key": "controller.out"},
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "actuator.inputSignal", "correct_symbol": "actuator.u", "candidate_key": "actuator.inputSignal"},
        ],
        "single_step_injection_replacements": [
            [("connect(controller.y, actuator.u);", "connect(controller.out, actuator.u);")],
            [("connect(controller.y, actuator.u);", "connect(controller.y, actuator.inputSignal);")],
        ],
        "injection_replacements": [("connect(controller.y, actuator.u);", "connect(controller.out, actuator.inputSignal);")],
    },
    {
        "task_id": "v0327_dual_medium_actuator_force_neighbor",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "placement_kind": "neighbor_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "actuator.out", "correct_symbol": "actuator.y", "candidate_key": "actuator.out"},
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "force.inputSignal", "correct_symbol": "force.f", "candidate_key": "force.inputSignal"},
        ],
        "single_step_injection_replacements": [
            [("connect(actuator.y, force.f);", "connect(actuator.out, force.f);")],
            [("connect(actuator.y, force.f);", "connect(actuator.y, force.inputSignal);")],
        ],
        "injection_replacements": [("connect(actuator.y, force.f);", "connect(actuator.out, force.inputSignal);")],
    },
    {
        "task_id": "v0327_dual_medium_controller_heatergain_neighbor",
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "placement_kind": "neighbor_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "controller.out", "correct_symbol": "controller.y", "candidate_key": "controller.out"},
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "heaterGain.inputSignal", "correct_symbol": "heaterGain.u", "candidate_key": "heaterGain.inputSignal"},
        ],
        "single_step_injection_replacements": [
            [("connect(controller.y, heaterGain.u);", "connect(controller.out, heaterGain.u);")],
            [("connect(controller.y, heaterGain.u);", "connect(controller.y, heaterGain.inputSignal);")],
        ],
        "injection_replacements": [("connect(controller.y, heaterGain.u);", "connect(controller.out, heaterGain.inputSignal);")],
    },
    {
        "task_id": "v0327_dual_medium_heatergain_heater_neighbor",
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "placement_kind": "neighbor_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "heaterGain.out", "correct_symbol": "heaterGain.y", "candidate_key": "heaterGain.out"},
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "heater.qIn", "correct_symbol": "heater.Q_flow", "candidate_key": "heater.qIn"},
        ],
        "single_step_injection_replacements": [
            [("connect(heaterGain.y, heater.Q_flow);", "connect(heaterGain.out, heater.Q_flow);")],
            [("connect(heaterGain.y, heater.Q_flow);", "connect(heaterGain.y, heater.qIn);")],
        ],
        "injection_replacements": [("connect(heaterGain.y, heater.Q_flow);", "connect(heaterGain.out, heater.qIn);")],
    },
    {
        "task_id": "v0327_dual_simple_source_resistor_neighbor",
        "source_id": "simple_electrical_sine_rl",
        "complexity_tier": "simple",
        "component_family": "local_connector_side_alignment",
        "placement_kind": "neighbor_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_connect_endpoint", "wrong_symbol": "source.posPin", "correct_symbol": "source.p", "candidate_key": "source.posPin"},
            {"patch_type": "replace_connect_endpoint", "wrong_symbol": "resistor.posPin", "correct_symbol": "resistor.p", "candidate_key": "resistor.posPin"},
        ],
        "single_step_injection_replacements": [
            [("connect(source.p, resistor.p);", "connect(source.posPin, resistor.p);")],
            [("connect(source.p, resistor.p);", "connect(source.p, resistor.posPin);")],
        ],
        "injection_replacements": [("connect(source.p, resistor.p);", "connect(source.posPin, resistor.posPin);")],
    },
    {
        "task_id": "v0327_dual_simple_resistor_inductor_neighbor",
        "source_id": "simple_electrical_sine_rl",
        "complexity_tier": "simple",
        "component_family": "local_connector_side_alignment",
        "placement_kind": "neighbor_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_connect_endpoint", "wrong_symbol": "resistor.negPin", "correct_symbol": "resistor.n", "candidate_key": "resistor.negPin"},
            {"patch_type": "replace_connect_endpoint", "wrong_symbol": "inductor.posPin", "correct_symbol": "inductor.p", "candidate_key": "inductor.posPin"},
        ],
        "single_step_injection_replacements": [
            [("connect(resistor.n, inductor.p);", "connect(resistor.negPin, inductor.p);")],
            [("connect(resistor.n, inductor.p);", "connect(resistor.n, inductor.posPin);")],
        ],
        "injection_replacements": [("connect(resistor.n, inductor.p);", "connect(resistor.negPin, inductor.posPin);")],
    },
    {
        "task_id": "v0327_dual_simple_resistor_ambient_neighbor",
        "source_id": "simple_thermal_heated_mass",
        "complexity_tier": "simple",
        "component_family": "local_connector_side_alignment",
        "placement_kind": "neighbor_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_connect_endpoint", "wrong_symbol": "resistor.portRight", "correct_symbol": "resistor.port_b", "candidate_key": "resistor.portRight"},
            {"patch_type": "replace_local_port_symbol", "wrong_symbol": "ambient.portHot", "correct_symbol": "ambient.port", "candidate_key": "ambient.portHot"},
        ],
        "single_step_injection_replacements": [
            [("connect(resistor.port_b, ambient.port);", "connect(resistor.portRight, ambient.port);")],
            [("connect(resistor.port_b, ambient.port);", "connect(resistor.port_b, ambient.portHot);")],
        ],
        "injection_replacements": [("connect(resistor.port_b, ambient.port);", "connect(resistor.portRight, ambient.portHot);")],
    },
]


def _single_from_dual_step(dual_spec: dict, step_index: int) -> dict:
    step = ((dual_spec.get("repair_steps") or [])[step_index]) if (dual_spec.get("repair_steps") or []) else {}
    replacements = ((dual_spec.get("single_step_injection_replacements") or [])[step_index]) if (dual_spec.get("single_step_injection_replacements") or []) else []
    return {
        "task_id": f"{norm(dual_spec.get('task_id')).replace('_dual_', '_single_', 1)}__step{step_index + 1}",
        "source_id": dual_spec.get("source_id"),
        "complexity_tier": dual_spec.get("complexity_tier"),
        "component_family": dual_spec.get("component_family"),
        "patch_type": step.get("patch_type"),
        "wrong_symbol": step.get("wrong_symbol"),
        "correct_symbol": step.get("correct_symbol"),
        "candidate_key": step.get("candidate_key"),
        "injection_replacements": list(replacements or []),
    }


SINGLE_MISMATCH_SPECS = [_single_from_dual_step(spec, step_index) for spec in DUAL_RECHECK_SPECS for step_index in range(len(spec.get("repair_steps") or []))]


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


def _extract_component_types(source_model_text: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    pattern = re.compile(r"^\s*(Modelica\.[A-Za-z0-9_.]+)\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
    for match in pattern.finditer(norm(source_model_text)):
        component_type = norm(match.group(1))
        component_name = norm(match.group(2))
        if component_type and component_name:
            mapping[component_name] = component_type
    return mapping


def _component_type_candidates(source_model_text: str, component_name: str) -> tuple[str, list[str]]:
    component_types = _extract_component_types(source_model_text)
    component_type = norm(component_types.get(norm(component_name)))
    members = COMPONENT_TYPE_LOCAL_SURFACE.get(component_type, [])
    return component_type, [f"{norm(component_name)}.{norm(member)}" for member in members if norm(member)]


def _symbol_occurrence_count(source_model_text: str, symbol: str) -> int:
    if not norm(symbol):
        return 0
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(norm(symbol))}(?![A-Za-z0-9_])")
    return len(pattern.findall(norm(source_model_text)))


def build_surface_index_payload(*, use_fixture_only: bool = False) -> dict:
    records: dict[str, dict] = {}
    export_failures: list[dict] = []
    source_specs = build_v0327_source_specs()
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
        source_model_text = norm(source.get("source_model_text"))
        component_name = _component_name(key)
        component_type, candidate_symbols = _component_type_candidates(source_model_text, component_name)
        canonical_symbol = norm(spec.get("correct_symbol"))
        canonical_occurrence_count = _symbol_occurrence_count(source_model_text, canonical_symbol)
        canonical_absent_elsewhere = canonical_occurrence_count <= 1
        if not component_type:
            export_failures.append(
                {
                    "candidate_key": key,
                    "source_id": norm(spec.get("source_id")),
                    "component_family": norm(spec.get("component_family")),
                    "reason": "missing_component_type_for_instance",
                }
            )
            continue
        if not candidate_symbols:
            export_failures.append(
                {
                    "candidate_key": key,
                    "source_id": norm(spec.get("source_id")),
                    "component_family": norm(spec.get("component_family")),
                    "component_type": component_type,
                    "reason": "empty_component_type_local_surface",
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
            "component_type": component_type,
            "canonical_symbol": canonical_symbol,
            "candidate_symbols": candidate_symbols,
            "canonical_source_occurrence_count": canonical_occurrence_count,
            "canonical_absent_elsewhere_from_source_model": canonical_absent_elsewhere,
        }
    success_count = len(records)
    total_count = len(seen_keys)
    return {
        "source_mode": "component_type_local_surface",
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
        record = local_surface_record_for(surface_index, norm(spec.get("candidate_key")))
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
                "candidate_symbols": candidate_symbols_for(surface_index, norm(spec.get("candidate_key"))),
                "component_type": norm(record.get("component_type")),
                "canonical_source_occurrence_count": int(record.get("canonical_source_occurrence_count") or 0),
                "canonical_absent_elsewhere_from_source_model": bool(record.get("canonical_absent_elsewhere_from_source_model")),
                "mutation_audit": audit,
                "discovery_mode": "authoritative_component_type_local_interface_surface",
                "source_task_origin": "neighbor_component_dual_step",
            }
        )
    return rows


def build_dual_task_rows(surface_index: dict) -> list[dict]:
    rows: list[dict] = []
    for spec in DUAL_RECHECK_SPECS:
        source = _source_row(spec.get("source_id"))
        mutated_model_text, audit = replacement_audit(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        repair_steps = []
        canonical_absent_elsewhere = True
        component_types: list[str] = []
        for step in spec.get("repair_steps") or []:
            record = local_surface_record_for(surface_index, norm(step.get("candidate_key")))
            canonical_absent_elsewhere = canonical_absent_elsewhere and bool(record.get("canonical_absent_elsewhere_from_source_model"))
            component_type = norm(record.get("component_type"))
            if component_type:
                component_types.append(component_type)
            repair_steps.append(
                {
                    "patch_type": norm(step.get("patch_type")),
                    "wrong_symbol": norm(step.get("wrong_symbol")),
                    "correct_symbol": norm(step.get("correct_symbol")),
                    "candidate_key": norm(step.get("candidate_key")),
                    "candidate_symbols": candidate_symbols_for(surface_index, norm(step.get("candidate_key"))),
                    "component_type": component_type,
                    "canonical_source_occurrence_count": int(record.get("canonical_source_occurrence_count") or 0),
                    "canonical_absent_elsewhere_from_source_model": bool(record.get("canonical_absent_elsewhere_from_source_model")),
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
                "component_type_set": component_types,
                "canonical_absent_elsewhere_from_source_model": canonical_absent_elsewhere,
                "mutation_audit": audit,
                "discovery_mode": "authoritative_component_type_local_interface_surface",
            }
        )
    return rows


def fixture_neighbor_post_first_fix_precheck_result() -> dict:
    return {
        "status": "PASS",
        "first_patch_applied": True,
        "second_residual_target_bucket_hit": True,
        "second_signature": "fixture_second_residual",
        "second_snapshot": {
            "dominant_stage_subtype": TARGET_STAGE_SUBTYPE,
            "error_subtype": TARGET_ERROR_SUBTYPE,
            "reason": "fixture_neighbor_post_first_fix_precheck",
        },
    }


def precheck_neighbor_dual_second_residual(task: dict, *, results_dir: str, timeout_sec: int = 600, use_fixture_only: bool = False) -> dict:
    if use_fixture_only:
        return fixture_neighbor_post_first_fix_precheck_result()
    repair_steps = task.get("repair_steps") or []
    if len(repair_steps) < 2:
        return {
            "status": "FAIL",
            "first_patch_applied": False,
            "second_residual_target_bucket_hit": False,
            "reason": "missing_second_repair_step",
        }
    first_step = repair_steps[0]
    patched_once_text, first_patch_audit = apply_interface_discovery_first_fix(
        current_text=norm(task.get("mutated_model_text")),
        patch_type=norm(first_step.get("patch_type")),
        wrong_symbol=norm(first_step.get("wrong_symbol")),
        canonical_symbol=norm(first_step.get("correct_symbol")),
        component_family=norm(task.get("component_family")),
        candidate_symbols=list(first_step.get("candidate_symbols") or []),
    )
    if not bool(first_patch_audit.get("applied")):
        return {
            "status": "FAIL",
            "first_patch_applied": False,
            "second_residual_target_bucket_hit": False,
            "reason": "first_patch_not_applied",
            "first_patch_audit": first_patch_audit,
        }
    rerun = rerun_once(
        task_id=f"{norm(task.get('task_id'))}__neighbor_precheck_after_first_fix",
        model_text=patched_once_text,
        result_dir=results_dir,
        evaluation_label="v0327_neighbor_precheck_after_first_fix",
        timeout_sec=timeout_sec,
    )
    detail = rerun.get("detail") if isinstance(rerun.get("detail"), dict) else {}
    second_signature, second_snapshot = first_attempt_signature(detail)
    target_bucket_hit = (
        norm(second_snapshot.get("dominant_stage_subtype")) == TARGET_STAGE_SUBTYPE
        and norm(second_snapshot.get("error_subtype")) == TARGET_ERROR_SUBTYPE
    )
    return {
        "status": "PASS" if target_bucket_hit else "FAIL",
        "first_patch_applied": True,
        "second_residual_target_bucket_hit": target_bucket_hit,
        "second_signature": second_signature,
        "second_snapshot": second_snapshot,
        "first_patch_audit": first_patch_audit,
        "result_json_path": rerun.get("result_json_path"),
    }


__all__ = [
    "COMPONENT_TYPE_LOCAL_SURFACE",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DUAL_RECHECK_OUT_DIR",
    "DEFAULT_DUAL_RECHECK_RESULTS_DIR",
    "DEFAULT_FIRST_FIX_OUT_DIR",
    "DEFAULT_FIRST_FIX_RESULTS_DIR",
    "DEFAULT_MANIFEST_OUT_DIR",
    "DEFAULT_PATCH_CONTRACT_OUT_DIR",
    "DEFAULT_SURFACE_AUDIT_OUT_DIR",
    "DEFAULT_SURFACE_INDEX_OUT_DIR",
    "DEFAULT_TASKSET_OUT_DIR",
    "DEFAULT_TASKSET_PRECHECK_RESULTS_DIR",
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
    "build_v0327_source_specs",
    "candidate_symbols_for",
    "classify_dry_run_output",
    "dry_run_dual_task",
    "dry_run_single_task",
    "fixture_dry_run_result",
    "fixture_neighbor_post_first_fix_precheck_result",
    "first_attempt_signature",
    "load_json",
    "local_surface_record_for",
    "norm",
    "now_utc",
    "precheck_neighbor_dual_second_residual",
    "rerun_once",
    "run_synthetic_task_live",
    "write_json",
    "write_text",
]
