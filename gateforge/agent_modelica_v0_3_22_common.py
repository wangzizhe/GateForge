from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_v0_3_19_common import DOCKER_IMAGE, build_source_specs as build_v0319_source_specs
from .agent_modelica_v0_3_20_common import first_attempt_signature, load_json, norm, rerun_once, replacement_audit, run_synthetic_task_live, write_json, write_text
from .agent_modelica_v0_3_21_common import (
    _collect_parameter_surface,
    _omc_eval,
    _parse_class_names,
    _strip_quotes,
    apply_discovery_first_fix,
)


SCHEMA_PREFIX = "agent_modelica_v0_3_22"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MANIFEST_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_22_coverage_manifest_current"
DEFAULT_SURFACE_INDEX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_22_surface_index_current"
DEFAULT_SURFACE_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_22_surface_export_audit_current"
DEFAULT_TASKSET_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_22_taskset_current"
DEFAULT_FIRST_FIX_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_22_first_fix_results_current"
DEFAULT_FIRST_FIX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_22_first_fix_evidence_current"
DEFAULT_DUAL_RECHECK_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_22_dual_recheck_results_current"
DEFAULT_DUAL_RECHECK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_22_dual_recheck_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_22_closeout_current"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


ADDITIONAL_SOURCE_SPECS = [
    {
        "source_id": "simple_electrical_sine_rl",
        "complexity_tier": "simple",
        "model_name": "ApiAlignSimpleElectricalSineRL",
        "source_model_text": "\n".join(
            [
                "model ApiAlignSimpleElectricalSineRL",
                "  Modelica.Electrical.Analog.Sources.SineVoltage source(V = 10.0, f = 50.0, phase = 0.0);",
                "  Modelica.Electrical.Analog.Basic.Resistor resistor(R = 10.0);",
                "  Modelica.Electrical.Analog.Basic.Inductor inductor(L = 0.1);",
                "  Modelica.Electrical.Analog.Basic.Ground ground;",
                "equation",
                "  connect(source.p, resistor.p);",
                "  connect(resistor.n, inductor.p);",
                "  connect(inductor.n, source.n);",
                "  connect(source.n, ground.p);",
                "end ApiAlignSimpleElectricalSineRL;",
            ]
        ),
    }
]


CLASS_QUERY_SPECS = {
    "Modelica.Blocks.Source.Sine": "Modelica.Blocks.Sources",
    "Modelica.Blocks.Source.Step": "Modelica.Blocks.Sources",
    "Modelica.Thermal.HeatTransfer.Components.FixedTemperature": "Modelica.Thermal.HeatTransfer.Sources",
    "Modelica.Blocks.Maths.Gain": "Modelica.Blocks.Math",
    "Modelica.Electrical.Analog.Source.SineVoltage": "Modelica.Electrical.Analog.Sources",
}


PARAMETER_QUERY_SPECS = {
    "Modelica.Blocks.Sources.Sine": ["amp", "freqHz"],
    "Modelica.Blocks.Sources.Step": ["amplitude", "startT"],
    "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature": ["temperature"],
    "Modelica.Blocks.Math.Gain": ["gain"],
    "Modelica.Electrical.Analog.Sources.SineVoltage": ["amplitude", "freqHz"],
}


SURFACE_INDEX_FIXTURE = {
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
        "Modelica.Blocks.Maths.Gain": [
            "Modelica.Blocks.Math.Gain",
            "Modelica.Blocks.Math.MatrixGain",
        ],
        "Modelica.Electrical.Analog.Source.SineVoltage": [
            "Modelica.Electrical.Analog.Sources.SineVoltage",
            "Modelica.Electrical.Analog.Sources.StepVoltage",
            "Modelica.Electrical.Analog.Sources.ConstantVoltage",
        ],
    },
    "parameter_surface_records": {
        repr(("Modelica.Blocks.Sources.Sine", "amp")): [
            {"name": "amplitude", "comment": "Amplitude of sine wave"},
            {"name": "f", "comment": "Frequency of sine wave"},
            {"name": "phase", "comment": "Phase of sine wave"},
            {"name": "continuous", "comment": "Make output continuous"},
        ],
        repr(("Modelica.Blocks.Sources.Sine", "freqHz")): [
            {"name": "amplitude", "comment": "Amplitude of sine wave"},
            {"name": "f", "comment": "Frequency of sine wave"},
            {"name": "phase", "comment": "Phase of sine wave"},
            {"name": "continuous", "comment": "Make output continuous"},
        ],
        repr(("Modelica.Blocks.Sources.Step", "amplitude")): [
            {"name": "height", "comment": "Height of step"},
            {"name": "offset", "comment": "Offset of output signal"},
            {"name": "startTime", "comment": "Output y = offset for time < startTime"},
        ],
        repr(("Modelica.Blocks.Sources.Step", "startT")): [
            {"name": "height", "comment": "Height of step"},
            {"name": "offset", "comment": "Offset of output signal"},
            {"name": "startTime", "comment": "Output y = offset for time < startTime"},
        ],
        repr(("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "temperature")): [
            {"name": "T", "comment": "Fixed temperature at port"},
        ],
        repr(("Modelica.Blocks.Math.Gain", "gain")): [
            {"name": "k", "comment": "Gain value multiplied with input signal"},
        ],
        repr(("Modelica.Electrical.Analog.Sources.SineVoltage", "amplitude")): [
            {"name": "V", "comment": "Amplitude of sine wave"},
            {"name": "phase", "comment": "Phase of sine wave"},
            {"name": "f", "comment": "Frequency of sine wave"},
        ],
        repr(("Modelica.Electrical.Analog.Sources.SineVoltage", "freqHz")): [
            {"name": "V", "comment": "Amplitude of sine wave"},
            {"name": "phase", "comment": "Phase of sine wave"},
            {"name": "f", "comment": "Frequency of sine wave"},
        ],
    },
}


TOKEN_EXPANSIONS = {
    "freq": ["frequency", "hz", "f"],
    "freqhz": ["frequency", "hz", "f"],
    "amp": ["amplitude", "magnitude", "height", "v"],
    "amplitude": ["amplitude", "magnitude", "height", "v"],
    "startt": ["start", "time", "starttime"],
    "temperature": ["temperature", "t"],
    "temp": ["temperature", "t"],
    "gain": ["gain", "k"],
}


SINGLE_MISMATCH_SPECS = [
    {
        "task_id": "v0322_single_simple_sine_class_path",
        "source_id": "simple_sine_driven_mass",
        "complexity_tier": "simple",
        "component_family": "blocks_source_sine",
        "patch_type": "replace_class_path",
        "component_type": "Modelica.Blocks.Sources.Sine",
        "wrong_symbol": "Modelica.Blocks.Source.Sine",
        "correct_symbol": "Modelica.Blocks.Sources.Sine",
        "injection_replacements": [("Modelica.Blocks.Sources.Sine", "Modelica.Blocks.Source.Sine")],
    },
    {
        "task_id": "v0322_single_simple_sine_param_amp",
        "source_id": "simple_sine_driven_mass",
        "complexity_tier": "simple",
        "component_family": "blocks_source_sine",
        "patch_type": "replace_parameter_name",
        "component_type": "Modelica.Blocks.Sources.Sine",
        "wrong_symbol": "amp",
        "correct_symbol": "amplitude",
        "injection_replacements": [("amplitude = 5.0", "amp = 5.0")],
    },
    {
        "task_id": "v0322_single_simple_sine_param_freq",
        "source_id": "simple_sine_driven_mass",
        "complexity_tier": "simple",
        "component_family": "blocks_source_sine",
        "patch_type": "replace_parameter_name",
        "component_type": "Modelica.Blocks.Sources.Sine",
        "wrong_symbol": "freqHz",
        "correct_symbol": "f",
        "injection_replacements": [("f = 0.5", "freqHz = 0.5")],
    },
    {
        "task_id": "v0322_single_simple_thermal_class_path",
        "source_id": "simple_thermal_heated_mass",
        "complexity_tier": "simple",
        "component_family": "thermal_fixed_temperature",
        "patch_type": "replace_class_path",
        "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
        "wrong_symbol": "Modelica.Thermal.HeatTransfer.Components.FixedTemperature",
        "correct_symbol": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
        "injection_replacements": [("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "Modelica.Thermal.HeatTransfer.Components.FixedTemperature")],
    },
    {
        "task_id": "v0322_single_simple_thermal_param_temperature",
        "source_id": "simple_thermal_heated_mass",
        "complexity_tier": "simple",
        "component_family": "thermal_fixed_temperature",
        "patch_type": "replace_parameter_name",
        "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
        "wrong_symbol": "temperature",
        "correct_symbol": "T",
        "injection_replacements": [("T = 293.15", "temperature = 293.15")],
    },
    {
        "task_id": "v0322_single_medium_step_class_path",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "blocks_source_step",
        "patch_type": "replace_class_path",
        "component_type": "Modelica.Blocks.Sources.Step",
        "wrong_symbol": "Modelica.Blocks.Source.Step",
        "correct_symbol": "Modelica.Blocks.Sources.Step",
        "injection_replacements": [("Modelica.Blocks.Sources.Step", "Modelica.Blocks.Source.Step")],
    },
    {
        "task_id": "v0322_single_medium_step_param_amplitude",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "blocks_source_step",
        "patch_type": "replace_parameter_name",
        "component_type": "Modelica.Blocks.Sources.Step",
        "wrong_symbol": "amplitude",
        "correct_symbol": "height",
        "injection_replacements": [("height = 1.0", "amplitude = 1.0")],
    },
    {
        "task_id": "v0322_single_medium_step_param_startt",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "blocks_source_step",
        "patch_type": "replace_parameter_name",
        "component_type": "Modelica.Blocks.Sources.Step",
        "wrong_symbol": "startT",
        "correct_symbol": "startTime",
        "requires_inherited_parameter": True,
        "injection_replacements": [("startTime = 0.5", "startT = 0.5")],
    },
    {
        "task_id": "v0322_single_medium_gain_class_path",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "blocks_math_gain",
        "patch_type": "replace_class_path",
        "component_type": "Modelica.Blocks.Math.Gain",
        "wrong_symbol": "Modelica.Blocks.Maths.Gain",
        "correct_symbol": "Modelica.Blocks.Math.Gain",
        "injection_replacements": [("Modelica.Blocks.Math.Gain actuator", "Modelica.Blocks.Maths.Gain actuator")],
    },
    {
        "task_id": "v0322_single_medium_gain_param_gain",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "blocks_math_gain",
        "patch_type": "replace_parameter_name",
        "component_type": "Modelica.Blocks.Math.Gain",
        "wrong_symbol": "gain",
        "correct_symbol": "k",
        "injection_replacements": [("k = 20.0", "gain = 20.0")],
    },
    {
        "task_id": "v0322_single_medium_thermal_class_path",
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "component_family": "thermal_fixed_temperature",
        "patch_type": "replace_class_path",
        "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
        "wrong_symbol": "Modelica.Thermal.HeatTransfer.Components.FixedTemperature",
        "correct_symbol": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
        "injection_replacements": [("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "Modelica.Thermal.HeatTransfer.Components.FixedTemperature")],
    },
    {
        "task_id": "v0322_single_medium_thermal_param_temperature",
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "component_family": "thermal_fixed_temperature",
        "patch_type": "replace_parameter_name",
        "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature",
        "wrong_symbol": "temperature",
        "correct_symbol": "T",
        "injection_replacements": [("T = 293.15", "temperature = 293.15")],
    },
    {
        "task_id": "v0322_single_simple_electrical_class_path",
        "source_id": "simple_electrical_sine_rl",
        "complexity_tier": "simple",
        "component_family": "electrical_sine_voltage",
        "patch_type": "replace_class_path",
        "component_type": "Modelica.Electrical.Analog.Sources.SineVoltage",
        "wrong_symbol": "Modelica.Electrical.Analog.Source.SineVoltage",
        "correct_symbol": "Modelica.Electrical.Analog.Sources.SineVoltage",
        "injection_replacements": [("Modelica.Electrical.Analog.Sources.SineVoltage", "Modelica.Electrical.Analog.Source.SineVoltage")],
    },
    {
        "task_id": "v0322_single_simple_electrical_param_amplitude",
        "source_id": "simple_electrical_sine_rl",
        "complexity_tier": "simple",
        "component_family": "electrical_sine_voltage",
        "patch_type": "replace_parameter_name",
        "component_type": "Modelica.Electrical.Analog.Sources.SineVoltage",
        "wrong_symbol": "amplitude",
        "correct_symbol": "V",
        "injection_replacements": [("V = 10.0", "amplitude = 10.0")],
    },
    {
        "task_id": "v0322_single_simple_electrical_param_freq",
        "source_id": "simple_electrical_sine_rl",
        "complexity_tier": "simple",
        "component_family": "electrical_sine_voltage",
        "patch_type": "replace_parameter_name",
        "component_type": "Modelica.Electrical.Analog.Sources.SineVoltage",
        "wrong_symbol": "freqHz",
        "correct_symbol": "f",
        "injection_replacements": [("f = 50.0", "freqHz = 50.0")],
    },
]


DUAL_MISMATCH_SPECS = [
    {
        "task_id": "v0322_dual_simple_sine_class_freq",
        "source_id": "simple_sine_driven_mass",
        "complexity_tier": "simple",
        "component_family": "blocks_source_sine",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_class_path", "component_type": "Modelica.Blocks.Sources.Sine", "wrong_symbol": "Modelica.Blocks.Source.Sine", "correct_symbol": "Modelica.Blocks.Sources.Sine"},
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Blocks.Sources.Sine", "wrong_symbol": "freqHz", "correct_symbol": "f"},
        ],
        "injection_replacements": [("Modelica.Blocks.Sources.Sine", "Modelica.Blocks.Source.Sine"), ("f = 0.5", "freqHz = 0.5")],
    },
    {
        "task_id": "v0322_dual_simple_sine_class_amp",
        "source_id": "simple_sine_driven_mass",
        "complexity_tier": "simple",
        "component_family": "blocks_source_sine",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_class_path", "component_type": "Modelica.Blocks.Sources.Sine", "wrong_symbol": "Modelica.Blocks.Source.Sine", "correct_symbol": "Modelica.Blocks.Sources.Sine"},
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Blocks.Sources.Sine", "wrong_symbol": "amp", "correct_symbol": "amplitude"},
        ],
        "injection_replacements": [("Modelica.Blocks.Sources.Sine", "Modelica.Blocks.Source.Sine"), ("amplitude = 5.0", "amp = 5.0")],
    },
    {
        "task_id": "v0322_dual_simple_sine_amp_freq",
        "source_id": "simple_sine_driven_mass",
        "complexity_tier": "simple",
        "component_family": "blocks_source_sine",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Blocks.Sources.Sine", "wrong_symbol": "amp", "correct_symbol": "amplitude"},
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Blocks.Sources.Sine", "wrong_symbol": "freqHz", "correct_symbol": "f"},
        ],
        "injection_replacements": [("amplitude = 5.0", "amp = 5.0"), ("f = 0.5", "freqHz = 0.5")],
    },
    {
        "task_id": "v0322_dual_simple_thermal_class_temperature",
        "source_id": "simple_thermal_heated_mass",
        "complexity_tier": "simple",
        "component_family": "thermal_fixed_temperature",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_class_path", "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "wrong_symbol": "Modelica.Thermal.HeatTransfer.Components.FixedTemperature", "correct_symbol": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature"},
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "wrong_symbol": "temperature", "correct_symbol": "T"},
        ],
        "injection_replacements": [("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "Modelica.Thermal.HeatTransfer.Components.FixedTemperature"), ("T = 293.15", "temperature = 293.15")],
    },
    {
        "task_id": "v0322_dual_medium_step_class_startt",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "blocks_source_step",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_class_path", "component_type": "Modelica.Blocks.Sources.Step", "wrong_symbol": "Modelica.Blocks.Source.Step", "correct_symbol": "Modelica.Blocks.Sources.Step"},
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Blocks.Sources.Step", "wrong_symbol": "startT", "correct_symbol": "startTime", "requires_inherited_parameter": True},
        ],
        "injection_replacements": [("Modelica.Blocks.Sources.Step", "Modelica.Blocks.Source.Step"), ("startTime = 0.5", "startT = 0.5")],
    },
    {
        "task_id": "v0322_dual_medium_step_class_amplitude",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "blocks_source_step",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_class_path", "component_type": "Modelica.Blocks.Sources.Step", "wrong_symbol": "Modelica.Blocks.Source.Step", "correct_symbol": "Modelica.Blocks.Sources.Step"},
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Blocks.Sources.Step", "wrong_symbol": "amplitude", "correct_symbol": "height"},
        ],
        "injection_replacements": [("Modelica.Blocks.Sources.Step", "Modelica.Blocks.Source.Step"), ("height = 1.0", "amplitude = 1.0")],
    },
    {
        "task_id": "v0322_dual_medium_step_amplitude_startt",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "blocks_source_step",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Blocks.Sources.Step", "wrong_symbol": "amplitude", "correct_symbol": "height"},
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Blocks.Sources.Step", "wrong_symbol": "startT", "correct_symbol": "startTime", "requires_inherited_parameter": True},
        ],
        "injection_replacements": [("height = 1.0", "amplitude = 1.0"), ("startTime = 0.5", "startT = 0.5")],
    },
    {
        "task_id": "v0322_dual_medium_gain_class_gain",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "component_family": "blocks_math_gain",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_class_path", "component_type": "Modelica.Blocks.Math.Gain", "wrong_symbol": "Modelica.Blocks.Maths.Gain", "correct_symbol": "Modelica.Blocks.Math.Gain"},
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Blocks.Math.Gain", "wrong_symbol": "gain", "correct_symbol": "k"},
        ],
        "injection_replacements": [("Modelica.Blocks.Math.Gain actuator", "Modelica.Blocks.Maths.Gain actuator"), ("k = 20.0", "gain = 20.0")],
    },
    {
        "task_id": "v0322_dual_medium_thermal_class_temperature",
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "component_family": "thermal_fixed_temperature",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_class_path", "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "wrong_symbol": "Modelica.Thermal.HeatTransfer.Components.FixedTemperature", "correct_symbol": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature"},
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "wrong_symbol": "temperature", "correct_symbol": "T"},
        ],
        "injection_replacements": [("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "Modelica.Thermal.HeatTransfer.Components.FixedTemperature"), ("T = 293.15", "temperature = 293.15")],
    },
    {
        "task_id": "v0322_dual_simple_electrical_class_freq",
        "source_id": "simple_electrical_sine_rl",
        "complexity_tier": "simple",
        "component_family": "electrical_sine_voltage",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_class_path", "component_type": "Modelica.Electrical.Analog.Sources.SineVoltage", "wrong_symbol": "Modelica.Electrical.Analog.Source.SineVoltage", "correct_symbol": "Modelica.Electrical.Analog.Sources.SineVoltage"},
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Electrical.Analog.Sources.SineVoltage", "wrong_symbol": "freqHz", "correct_symbol": "f"},
        ],
        "injection_replacements": [("Modelica.Electrical.Analog.Sources.SineVoltage", "Modelica.Electrical.Analog.Source.SineVoltage"), ("f = 50.0", "freqHz = 50.0")],
    },
    {
        "task_id": "v0322_dual_simple_electrical_class_amplitude",
        "source_id": "simple_electrical_sine_rl",
        "complexity_tier": "simple",
        "component_family": "electrical_sine_voltage",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_class_path", "component_type": "Modelica.Electrical.Analog.Sources.SineVoltage", "wrong_symbol": "Modelica.Electrical.Analog.Source.SineVoltage", "correct_symbol": "Modelica.Electrical.Analog.Sources.SineVoltage"},
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Electrical.Analog.Sources.SineVoltage", "wrong_symbol": "amplitude", "correct_symbol": "V"},
        ],
        "injection_replacements": [("Modelica.Electrical.Analog.Sources.SineVoltage", "Modelica.Electrical.Analog.Source.SineVoltage"), ("V = 10.0", "amplitude = 10.0")],
    },
    {
        "task_id": "v0322_dual_simple_electrical_amplitude_freq",
        "source_id": "simple_electrical_sine_rl",
        "complexity_tier": "simple",
        "component_family": "electrical_sine_voltage",
        "placement_kind": "same_component_dual_mismatch",
        "repair_steps": [
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Electrical.Analog.Sources.SineVoltage", "wrong_symbol": "amplitude", "correct_symbol": "V"},
            {"patch_type": "replace_parameter_name", "component_type": "Modelica.Electrical.Analog.Sources.SineVoltage", "wrong_symbol": "freqHz", "correct_symbol": "f"},
        ],
        "injection_replacements": [("V = 10.0", "amplitude = 10.0"), ("f = 50.0", "freqHz = 50.0")],
    },
]


def build_v0322_source_specs() -> list[dict]:
    rows = [dict(row) for row in build_v0319_source_specs()]
    rows.extend(dict(row) for row in ADDITIONAL_SOURCE_SPECS)
    return rows


def _source_row(source_id: str) -> dict:
    for row in build_v0322_source_specs():
        if norm(row.get("source_id")) == norm(source_id):
            return row
    return {}


def _parameter_key(class_name: str, wrong_symbol: str) -> str:
    return repr((norm(class_name), norm(wrong_symbol)))


def build_surface_index_payload(*, use_fixture_only: bool = False) -> dict:
    if use_fixture_only:
        return {
            "source_mode": "fixture_fallback",
            "omc_backend": "openmodelica_docker",
            "docker_image": DOCKER_IMAGE,
            "modelica_version": norm(SURFACE_INDEX_FIXTURE.get("modelica_version")),
            "class_path_candidates": dict(SURFACE_INDEX_FIXTURE.get("class_path_candidates") or {}),
            "parameter_surface_records": dict(SURFACE_INDEX_FIXTURE.get("parameter_surface_records") or {}),
            "class_provenance": {norm(key): "fixture_fallback" for key in (SURFACE_INDEX_FIXTURE.get("class_path_candidates") or {}).keys()},
            "parameter_provenance": {norm(key): "fixture_fallback" for key in (SURFACE_INDEX_FIXTURE.get("parameter_surface_records") or {}).keys()},
        }
    modelica_version = _strip_quotes(_omc_eval("getVersion(Modelica)")) or norm(SURFACE_INDEX_FIXTURE.get("modelica_version"))
    class_path_candidates: dict[str, list[str]] = {}
    parameter_surface_records: dict[str, list[dict]] = {}
    class_provenance: dict[str, str] = {}
    parameter_provenance: dict[str, str] = {}
    for wrong_symbol, package_name in CLASS_QUERY_SPECS.items():
        payload = _omc_eval(f"getClassNames({package_name})")
        class_names = _parse_class_names(payload)
        if class_names:
            class_path_candidates[wrong_symbol] = [f"{package_name}.{name}" for name in class_names]
            class_provenance[wrong_symbol] = "omc_export"
        else:
            class_path_candidates[wrong_symbol] = list((SURFACE_INDEX_FIXTURE.get("class_path_candidates") or {}).get(wrong_symbol) or [])
            class_provenance[wrong_symbol] = "fixture_fallback"
    for class_name, wrong_symbols in PARAMETER_QUERY_SPECS.items():
        rows = _collect_parameter_surface(class_name)
        for wrong_symbol in wrong_symbols:
            key = _parameter_key(class_name, wrong_symbol)
            if rows:
                parameter_surface_records[key] = rows
                parameter_provenance[key] = "omc_export"
            else:
                parameter_surface_records[key] = list((SURFACE_INDEX_FIXTURE.get("parameter_surface_records") or {}).get(key) or [])
                parameter_provenance[key] = "fixture_fallback"
    return {
        "source_mode": "mixed" if "fixture_fallback" in set(class_provenance.values()) | set(parameter_provenance.values()) else "omc_export",
        "omc_backend": "openmodelica_docker",
        "docker_image": DOCKER_IMAGE,
        "modelica_version": modelica_version,
        "class_path_candidates": class_path_candidates,
        "parameter_surface_records": parameter_surface_records,
        "class_provenance": class_provenance,
        "parameter_provenance": parameter_provenance,
    }


def class_candidates_for(surface_index: dict, wrong_symbol: str) -> list[str]:
    candidates = surface_index.get("class_path_candidates") if isinstance(surface_index.get("class_path_candidates"), dict) else {}
    rows = candidates.get(norm(wrong_symbol))
    return [norm(item) for item in rows if norm(item)] if isinstance(rows, list) else []


def parameter_records_for(surface_index: dict, component_type: str, wrong_symbol: str) -> list[dict]:
    records = surface_index.get("parameter_surface_records") if isinstance(surface_index.get("parameter_surface_records"), dict) else {}
    rows = records.get(_parameter_key(component_type, wrong_symbol))
    if not isinstance(rows, list):
        return []
    clean_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        clean_rows.append({"name": norm(row.get("name")), "comment": norm(row.get("comment"))})
    return clean_rows


def candidate_provenance_for(surface_index: dict, patch_type: str, component_type: str, wrong_symbol: str) -> str:
    if patch_type == "replace_class_path":
        prov = surface_index.get("class_provenance") if isinstance(surface_index.get("class_provenance"), dict) else {}
        return norm(prov.get(norm(wrong_symbol)))
    prov = surface_index.get("parameter_provenance") if isinstance(surface_index.get("parameter_provenance"), dict) else {}
    return norm(prov.get(_parameter_key(component_type, wrong_symbol)))


def build_single_task_rows(surface_index: dict) -> list[dict]:
    rows = []
    for spec in SINGLE_MISMATCH_SPECS:
        source = _source_row(spec.get("source_id"))
        mutated_model_text, audit = replacement_audit(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        patch_type = norm(spec.get("patch_type"))
        component_type = norm(spec.get("component_type"))
        wrong_symbol = norm(spec.get("wrong_symbol"))
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
                "patch_type": patch_type,
                "component_type": component_type,
                "wrong_symbol": wrong_symbol,
                "correct_symbol": norm(spec.get("correct_symbol")),
                "class_path_candidates": class_candidates_for(surface_index, wrong_symbol),
                "candidate_parameter_records": parameter_records_for(surface_index, component_type, wrong_symbol),
                "candidate_provenance": candidate_provenance_for(surface_index, patch_type, component_type, wrong_symbol),
                "requires_inherited_parameter": bool(spec.get("requires_inherited_parameter")),
                "mutation_audit": audit,
            }
        )
    return rows


def build_dual_task_rows(surface_index: dict) -> list[dict]:
    rows = []
    for spec in DUAL_MISMATCH_SPECS:
        source = _source_row(spec.get("source_id"))
        mutated_model_text, audit = replacement_audit(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        repair_steps = []
        for step in spec.get("repair_steps") or []:
            patch_type = norm(step.get("patch_type"))
            component_type = norm(step.get("component_type"))
            wrong_symbol = norm(step.get("wrong_symbol"))
            repair_steps.append(
                {
                    "patch_type": patch_type,
                    "component_type": component_type,
                    "wrong_symbol": wrong_symbol,
                    "correct_symbol": norm(step.get("correct_symbol")),
                    "class_path_candidates": class_candidates_for(surface_index, wrong_symbol),
                    "candidate_parameter_records": parameter_records_for(surface_index, component_type, wrong_symbol),
                    "candidate_provenance": candidate_provenance_for(surface_index, patch_type, component_type, wrong_symbol),
                    "requires_inherited_parameter": bool(step.get("requires_inherited_parameter")),
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
