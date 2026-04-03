from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_omc_workspace_v1 import run_omc_script_docker, temporary_workspace
from .agent_modelica_v0_3_19_common import (
    DOCKER_IMAGE,
    build_source_specs as build_v0319_source_specs,
    error_signature_from_text,
)
from .agent_modelica_v0_3_20_common import (
    first_attempt_signature,
    load_json,
    norm,
    replacement_audit,
    rerun_once,
    run_synthetic_task_live,
    write_json,
    write_text,
)


SCHEMA_PREFIX = "agent_modelica_v0_3_23"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TARGET_MANIFEST_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_23_target_manifest_current"
DEFAULT_PATCH_CONTRACT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_23_patch_contract_current"
DEFAULT_FIRST_FIX_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_23_first_fix_results_current"
DEFAULT_FIRST_FIX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_23_first_fix_evidence_current"
DEFAULT_DUAL_RECHECK_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_23_dual_recheck_results_current"
DEFAULT_DUAL_RECHECK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_23_dual_recheck_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_23_closeout_current"

TARGET_STAGE_SUBTYPE = "stage_2_structural_balance_reference"
TARGET_ERROR_SUBTYPE = "undefined_symbol"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


ADDITIONAL_SOURCE_SPECS = [
    {
        "source_id": "simple_electrical_sine_rl",
        "complexity_tier": "simple",
        "model_name": "InterfaceAlignSimpleElectricalSineRL",
        "source_model_text": "\n".join(
            [
                "model InterfaceAlignSimpleElectricalSineRL",
                "  Modelica.Electrical.Analog.Sources.SineVoltage source(V = 10.0, f = 50.0, phase = 0.0);",
                "  Modelica.Electrical.Analog.Basic.Resistor resistor(R = 10.0);",
                "  Modelica.Electrical.Analog.Basic.Inductor inductor(L = 0.1);",
                "  Modelica.Electrical.Analog.Basic.Ground ground;",
                "equation",
                "  connect(source.p, resistor.p);",
                "  connect(resistor.n, inductor.p);",
                "  connect(inductor.n, source.n);",
                "  connect(source.n, ground.p);",
                "end InterfaceAlignSimpleElectricalSineRL;",
            ]
        ),
    }
]


LOCAL_INTERFACE_CANDIDATES = {
    "sine.outSig": {
        "correct_symbol": "sine.y",
        "candidate_symbols": ["sine.y"],
    },
    "Q_flow.outSig": {
        "correct_symbol": "Q_flow.y",
        "candidate_symbols": ["Q_flow.y"],
    },
    "heater.qIn": {
        "correct_symbol": "heater.Q_flow",
        "candidate_symbols": ["heater.Q_flow"],
    },
    "feedback.input1": {
        "correct_symbol": "feedback.u1",
        "candidate_symbols": ["feedback.u1", "feedback.u2", "feedback.y"],
    },
    "feedback.outSig": {
        "correct_symbol": "feedback.y",
        "candidate_symbols": ["feedback.y", "feedback.u1", "feedback.u2"],
    },
    "heaterGain.inputSignal": {
        "correct_symbol": "heaterGain.u",
        "candidate_symbols": ["heaterGain.u", "heaterGain.y"],
    },
    "heaterGain.out": {
        "correct_symbol": "heaterGain.y",
        "candidate_symbols": ["heaterGain.y", "heaterGain.u"],
    },
    "wall.portLeft": {
        "correct_symbol": "wall.port_a",
        "candidate_symbols": ["wall.port_a", "wall.port_b"],
    },
    "wall.portRight": {
        "correct_symbol": "wall.port_b",
        "candidate_symbols": ["wall.port_b", "wall.port_a"],
    },
    "source.posPin": {
        "correct_symbol": "source.p",
        "candidate_symbols": ["source.p", "source.n"],
    },
    "source.negPin": {
        "correct_symbol": "source.n",
        "candidate_symbols": ["source.n", "source.p"],
    },
}


SINGLE_MISMATCH_SPECS = [
    {
        "task_id": "v0323_single_simple_sine_outsig",
        "source_id": "simple_sine_driven_mass",
        "complexity_tier": "simple",
        "component_family": "local_signal_port_alignment",
        "patch_type": "replace_local_port_symbol",
        "wrong_symbol": "sine.outSig",
        "correct_symbol": "sine.y",
        "candidate_key": "sine.outSig",
        "injection_replacements": [("connect(sine.y, force.f);", "connect(sine.outSig, force.f);")],
    },
    {
        "task_id": "v0323_single_simple_thermal_qflow_outsig",
        "source_id": "simple_thermal_heated_mass",
        "complexity_tier": "simple",
        "component_family": "local_signal_port_alignment",
        "patch_type": "replace_local_port_symbol",
        "wrong_symbol": "Q_flow.outSig",
        "correct_symbol": "Q_flow.y",
        "candidate_key": "Q_flow.outSig",
        "injection_replacements": [("connect(Q_flow.y, heater.Q_flow);", "connect(Q_flow.outSig, heater.Q_flow);")],
    },
    {
        "task_id": "v0323_single_simple_thermal_heater_qin",
        "source_id": "simple_thermal_heated_mass",
        "complexity_tier": "simple",
        "component_family": "local_signal_port_alignment",
        "patch_type": "replace_local_port_symbol",
        "wrong_symbol": "heater.qIn",
        "correct_symbol": "heater.Q_flow",
        "candidate_key": "heater.qIn",
        "injection_replacements": [("connect(Q_flow.y, heater.Q_flow);", "connect(Q_flow.y, heater.qIn);")],
    },
    {
        "task_id": "v0323_single_medium_feedback_input1",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "patch_type": "replace_local_port_symbol",
        "wrong_symbol": "feedback.input1",
        "correct_symbol": "feedback.u1",
        "candidate_key": "feedback.input1",
        "injection_replacements": [("connect(reference.y, feedback.u1);", "connect(reference.y, feedback.input1);")],
    },
    {
        "task_id": "v0323_single_medium_feedback_outsig",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "patch_type": "replace_local_port_symbol",
        "wrong_symbol": "feedback.outSig",
        "correct_symbol": "feedback.y",
        "candidate_key": "feedback.outSig",
        "injection_replacements": [("connect(feedback.y, controller.u);", "connect(feedback.outSig, controller.u);")],
    },
    {
        "task_id": "v0323_single_medium_heatergain_inputsignal",
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "patch_type": "replace_local_port_symbol",
        "wrong_symbol": "heaterGain.inputSignal",
        "correct_symbol": "heaterGain.u",
        "candidate_key": "heaterGain.inputSignal",
        "injection_replacements": [("connect(controller.y, heaterGain.u);", "connect(controller.y, heaterGain.inputSignal);")],
    },
    {
        "task_id": "v0323_single_medium_heatergain_out",
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "patch_type": "replace_local_port_symbol",
        "wrong_symbol": "heaterGain.out",
        "correct_symbol": "heaterGain.y",
        "candidate_key": "heaterGain.out",
        "injection_replacements": [("connect(heaterGain.y, heater.Q_flow);", "connect(heaterGain.out, heater.Q_flow);")],
    },
    {
        "task_id": "v0323_single_medium_wall_portleft",
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "component_family": "local_connector_side_alignment",
        "patch_type": "replace_connect_endpoint",
        "wrong_symbol": "wall.portLeft",
        "correct_symbol": "wall.port_a",
        "candidate_key": "wall.portLeft",
        "injection_replacements": [("connect(room.port, wall.port_a);", "connect(room.port, wall.portLeft);")],
    },
    {
        "task_id": "v0323_single_medium_wall_portright",
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "component_family": "local_connector_side_alignment",
        "patch_type": "replace_connect_endpoint",
        "wrong_symbol": "wall.portRight",
        "correct_symbol": "wall.port_b",
        "candidate_key": "wall.portRight",
        "injection_replacements": [("connect(wall.port_b, ambient.port);", "connect(wall.portRight, ambient.port);")],
    },
    {
        "task_id": "v0323_single_simple_electrical_pospin",
        "source_id": "simple_electrical_sine_rl",
        "complexity_tier": "simple",
        "component_family": "local_connector_side_alignment",
        "patch_type": "replace_connect_endpoint",
        "wrong_symbol": "source.posPin",
        "correct_symbol": "source.p",
        "candidate_key": "source.posPin",
        "injection_replacements": [("connect(source.p, resistor.p);", "connect(source.posPin, resistor.p);")],
    },
    {
        "task_id": "v0323_single_simple_electrical_negpin",
        "source_id": "simple_electrical_sine_rl",
        "complexity_tier": "simple",
        "component_family": "local_connector_side_alignment",
        "patch_type": "replace_connect_endpoint",
        "wrong_symbol": "source.negPin",
        "correct_symbol": "source.n",
        "candidate_key": "source.negPin",
        "injection_replacements": [("connect(inductor.n, source.n);", "connect(inductor.n, source.negPin);")],
    },
]


DUAL_RECHECK_SPECS = [
    {
        "task_id": "v0323_dual_simple_thermal_signal_cluster",
        "source_id": "simple_thermal_heated_mass",
        "complexity_tier": "simple",
        "component_family": "local_signal_port_alignment",
        "placement_kind": "same_local_cluster_dual_mismatch",
        "repair_steps": [
            {
                "patch_type": "replace_local_port_symbol",
                "wrong_symbol": "Q_flow.outSig",
                "correct_symbol": "Q_flow.y",
                "candidate_key": "Q_flow.outSig",
            },
            {
                "patch_type": "replace_local_port_symbol",
                "wrong_symbol": "heater.qIn",
                "correct_symbol": "heater.Q_flow",
                "candidate_key": "heater.qIn",
            },
        ],
        "injection_replacements": [
            ("connect(Q_flow.y, heater.Q_flow);", "connect(Q_flow.outSig, heater.qIn);"),
        ],
    },
    {
        "task_id": "v0323_dual_medium_feedback_component",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {
                "patch_type": "replace_local_port_symbol",
                "wrong_symbol": "feedback.input1",
                "correct_symbol": "feedback.u1",
                "candidate_key": "feedback.input1",
            },
            {
                "patch_type": "replace_local_port_symbol",
                "wrong_symbol": "feedback.outSig",
                "correct_symbol": "feedback.y",
                "candidate_key": "feedback.outSig",
            },
        ],
        "injection_replacements": [
            ("connect(reference.y, feedback.u1);", "connect(reference.y, feedback.input1);"),
            ("connect(feedback.y, controller.u);", "connect(feedback.outSig, controller.u);"),
        ],
    },
    {
        "task_id": "v0323_dual_medium_heatergain_component",
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "component_family": "local_signal_port_alignment",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {
                "patch_type": "replace_local_port_symbol",
                "wrong_symbol": "heaterGain.inputSignal",
                "correct_symbol": "heaterGain.u",
                "candidate_key": "heaterGain.inputSignal",
            },
            {
                "patch_type": "replace_local_port_symbol",
                "wrong_symbol": "heaterGain.out",
                "correct_symbol": "heaterGain.y",
                "candidate_key": "heaterGain.out",
            },
        ],
        "injection_replacements": [
            ("connect(controller.y, heaterGain.u);", "connect(controller.y, heaterGain.inputSignal);"),
            ("connect(heaterGain.y, heater.Q_flow);", "connect(heaterGain.out, heater.Q_flow);"),
        ],
    },
    {
        "task_id": "v0323_dual_medium_wall_component",
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "component_family": "local_connector_side_alignment",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {
                "patch_type": "replace_connect_endpoint",
                "wrong_symbol": "wall.portLeft",
                "correct_symbol": "wall.port_a",
                "candidate_key": "wall.portLeft",
            },
            {
                "patch_type": "replace_connect_endpoint",
                "wrong_symbol": "wall.portRight",
                "correct_symbol": "wall.port_b",
                "candidate_key": "wall.portRight",
            },
        ],
        "injection_replacements": [
            ("connect(room.port, wall.port_a);", "connect(room.port, wall.portLeft);"),
            ("connect(wall.port_b, ambient.port);", "connect(wall.portRight, ambient.port);"),
        ],
    },
    {
        "task_id": "v0323_dual_simple_electrical_source_component",
        "source_id": "simple_electrical_sine_rl",
        "complexity_tier": "simple",
        "component_family": "local_connector_side_alignment",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {
                "patch_type": "replace_connect_endpoint",
                "wrong_symbol": "source.posPin",
                "correct_symbol": "source.p",
                "candidate_key": "source.posPin",
            },
            {
                "patch_type": "replace_connect_endpoint",
                "wrong_symbol": "source.negPin",
                "correct_symbol": "source.n",
                "candidate_key": "source.negPin",
            },
        ],
        "injection_replacements": [
            ("connect(source.p, resistor.p);", "connect(source.posPin, resistor.p);"),
            ("connect(inductor.n, source.n);", "connect(inductor.n, source.negPin);"),
        ],
    },
]


def build_v0323_source_specs() -> list[dict]:
    rows = [dict(row) for row in build_v0319_source_specs()]
    rows.extend(dict(row) for row in ADDITIONAL_SOURCE_SPECS)
    return rows


def _source_row(source_id: str) -> dict:
    for row in build_v0323_source_specs():
        if norm(row.get("source_id")) == norm(source_id):
            return row
    return {}


def candidate_symbols_for(candidate_key: str) -> list[str]:
    payload = LOCAL_INTERFACE_CANDIDATES.get(norm(candidate_key)) or {}
    return [norm(item) for item in payload.get("candidate_symbols") or [] if norm(item)]


def canonical_symbol_for(candidate_key: str) -> str:
    payload = LOCAL_INTERFACE_CANDIDATES.get(norm(candidate_key)) or {}
    return norm(payload.get("correct_symbol"))


def apply_interface_first_fix(*, current_text: str, patch_type: str, wrong_symbol: str, candidate_key: str) -> tuple[str, dict]:
    current = str(current_text or "")
    candidates = candidate_symbols_for(candidate_key)
    selected = candidates[0] if candidates else ""
    canonical = canonical_symbol_for(candidate_key)
    if wrong_symbol not in current:
        return current, {
            "applied": False,
            "reason": "wrong_symbol_not_found_in_text",
            "selected_candidate": selected,
            "candidate_symbols": candidates,
            "candidate_top1_is_canonical": bool(selected and selected == canonical),
        }
    if not selected:
        return current, {
            "applied": False,
            "reason": "candidate_set_empty",
            "selected_candidate": "",
            "candidate_symbols": candidates,
            "candidate_top1_is_canonical": False,
        }
    patched = current.replace(wrong_symbol, selected, 1)
    return patched, {
        "applied": patched != current,
        "reason": "applied_interface_patch" if patched != current else "text_unchanged_after_patch",
        "selected_candidate": selected,
        "candidate_symbols": candidates,
        "candidate_top1_is_canonical": bool(selected and selected == canonical),
        "patch_type": norm(patch_type),
        "wrong_symbol": norm(wrong_symbol),
    }


def _dry_run_check(model_name: str, model_text: str, timeout_sec: int = 120) -> dict:
    script = "\n".join(
        [
            "loadModel(Modelica);",
            'loadFile("model.mo");',
            f"checkModel({model_name});",
            "getErrorString();",
            "",
        ]
    )
    with temporary_workspace("v0323_dry_run_") as td:
        target = Path(td) / "model.mo"
        target.write_text(model_text, encoding="utf-8")
        rc, output = run_omc_script_docker(
            script_text=script,
            timeout_sec=timeout_sec,
            cwd=td,
            image=DOCKER_IMAGE,
        )
    return classify_dry_run_output(output=str(output or ""), return_code=int(rc))


def classify_dry_run_output(*, output: str, return_code: int) -> dict:
    signature = error_signature_from_text(output)
    content = norm(output)
    if "Variable " in content and " not found in scope" in content:
        bucket = "stage_2_local_interface_alignment"
        stage = TARGET_STAGE_SUBTYPE
        subtype = TARGET_ERROR_SUBTYPE
    elif "No viable alternative" in content or "Parser error" in content:
        bucket = "stage_1_parse_error"
        stage = "stage_1_parse"
        subtype = "parse_error"
    elif signature:
        bucket = "compile_failure_unknown"
        stage = "stage_2_structural_balance_reference"
        subtype = "compile_failure_unknown"
    else:
        bucket = "none"
        stage = "stage_0_none"
        subtype = "none"
    return {
        "return_code": int(return_code),
        "error_signature": signature,
        "dry_run_bucket": bucket,
        "dominant_stage_subtype": stage,
        "error_subtype": subtype,
        "target_bucket_hit": stage == TARGET_STAGE_SUBTYPE and subtype == TARGET_ERROR_SUBTYPE,
        "output_excerpt": content[:500],
    }


def build_single_task_rows() -> list[dict]:
    rows = []
    for spec in SINGLE_MISMATCH_SPECS:
        source = _source_row(spec.get("source_id"))
        mutated_model_text, audit = replacement_audit(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
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
                "candidate_symbols": candidate_symbols_for(norm(spec.get("candidate_key"))),
                "mutation_audit": audit,
            }
        )
    return rows


def build_dual_task_rows() -> list[dict]:
    rows = []
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
                    "candidate_symbols": candidate_symbols_for(norm(step.get("candidate_key"))),
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
                "declared_failure_type": "model_check_error",
                "expected_stage": "check",
                "repair_steps": repair_steps,
                "mutation_audit": audit,
            }
        )
    return rows


def dry_run_single_task(task: dict) -> dict:
    return _dry_run_check(norm(task.get("model_name")), norm(task.get("mutated_model_text")))


def dry_run_dual_task(task: dict) -> dict:
    return _dry_run_check(norm(task.get("model_name")), norm(task.get("mutated_model_text")))


def fixture_dry_run_result() -> dict:
    return {
        "return_code": 0,
        "error_signature": "Error: Variable placeholder not found in scope FixtureModel.",
        "dry_run_bucket": "stage_2_local_interface_alignment",
        "dominant_stage_subtype": TARGET_STAGE_SUBTYPE,
        "error_subtype": TARGET_ERROR_SUBTYPE,
        "target_bucket_hit": True,
        "output_excerpt": "Fixture dry run result for unit tests.",
    }
