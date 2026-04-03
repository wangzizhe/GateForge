from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_l2_plan_replan_engine_v1 import send_with_budget
from .agent_modelica_runtime_context_v1 import AgentModelicaRuntimeContext, resolve_planner_backend_from_env
from .agent_modelica_v0_3_14_step_experience_common import action_type_from_row, norm, residual_signal_cluster
from .llm_provider_adapter import resolve_provider_adapter
from .llm_response import extract_json_object


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKER_IMAGE = os.environ.get("GATEFORGE_DOCKER_IMAGE", "openmodelica/openmodelica:v1.26.1-minimal")


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


def planner_backend() -> str:
    backend = str(resolve_planner_backend_from_env() or "").strip().lower()
    if backend:
        return backend
    adapter, config = resolve_provider_adapter("")
    return str(config.provider_name or adapter.provider_name).strip().lower()


@dataclass(frozen=True)
class PromptSpec:
    task_id: str
    complexity_tier: str
    model_name: str
    natural_language_spec: str
    expected_domain_tags: tuple[str, ...]
    expected_component_count_band: str
    allowed_library_scope: str = "Modelica Standard Library only"

    def to_dict(self, *, role: str, ordinal: int) -> dict:
        return {
            "task_id": self.task_id,
            "role": role,
            "ordinal_within_tier": int(ordinal),
            "complexity_tier": self.complexity_tier,
            "model_name": self.model_name,
            "natural_language_spec": self.natural_language_spec,
            "expected_domain_tags": list(self.expected_domain_tags),
            "expected_component_count_band": self.expected_component_count_band,
            "allowed_library_scope": self.allowed_library_scope,
        }


def _spec(task_id: str, tier: str, model_name: str, tags: tuple[str, ...], band: str, prompt: str) -> PromptSpec:
    return PromptSpec(
        task_id=task_id,
        complexity_tier=tier,
        model_name=model_name,
        natural_language_spec=prompt,
        expected_domain_tags=tags,
        expected_component_count_band=band,
    )


SIMPLE_SPECS: tuple[PromptSpec, ...] = (
    _spec("gen_simple_rlc_step_response", "simple", "SimpleRLCStepResponse", ("electrical",), "3-5", "Build a self-contained Modelica model of a series RLC circuit driven by a step voltage source. Include the source, resistor, inductor, capacitor, and a way to observe capacitor voltage."),
    _spec("gen_simple_rc_lowpass_filter", "simple", "SimpleRCLowpassFilter", ("electrical",), "3-5", "Build a self-contained Modelica model of an RC low-pass filter driven by a sine source. Include the source, resistor, capacitor, ground, and an output signal for the capacitor voltage."),
    _spec("gen_simple_mass_spring_damper", "simple", "SimpleMassSpringDamper", ("mechanical",), "3-5", "Build a self-contained translational mass-spring-damper Modelica model driven by a step force. Include the force source, mass, spring, damper, and a position output."),
    _spec("gen_simple_rotational_inertia_damper", "simple", "SimpleRotationalInertiaDamper", ("mechanical",), "3-5", "Build a self-contained rotational Modelica model with an inertia, spring, and damper driven by a torque step. Include a speed output."),
    _spec("gen_simple_thermal_heated_mass", "simple", "SimpleThermalHeatedMass", ("thermal",), "3-5", "Build a self-contained thermal Modelica model with a heated thermal mass connected to ambient through a thermal resistor. Include a heater input and a temperature output."),
    _spec("gen_simple_translational_force_mass", "simple", "SimpleTranslationalForceMass", ("mechanical",), "3-5", "Build a self-contained translational Modelica model of a mass driven by a force source and connected to a spring to ground. Include displacement output."),
    _spec("gen_simple_two_inertia_shaft", "simple", "SimpleTwoInertiaShaft", ("mechanical",), "3-5", "Build a self-contained rotational Modelica model with two inertias connected by a compliant shaft and a torque source on one side. Include both angular speeds as outputs."),
    _spec("gen_simple_thermal_wall_room", "simple", "SimpleThermalWallRoom", ("thermal",), "3-5", "Build a self-contained thermal Modelica model of one room thermal mass connected to ambient through a wall thermal resistance and heated by a fixed heat flow. Include room temperature output."),
    _spec("gen_simple_series_rl_load", "simple", "SimpleSeriesRLLoad", ("electrical",), "3-5", "Build a self-contained Modelica model of a series RL load driven by a square-wave voltage source. Include current measurement output."),
    _spec("gen_simple_sine_driven_mass", "simple", "SimpleSineDrivenMass", ("mechanical",), "3-5", "Build a self-contained translational Modelica model of a mass-spring-damper system excited by a sine force input. Include position and velocity outputs."),
    _spec("gen_simple_heat_capacity_cooler", "simple", "SimpleHeatCapacityCooler", ("thermal",), "3-5", "Build a self-contained thermal Modelica model with a heat capacity cooled through a thermal resistor and disturbed by a heat source. Include temperature output."),
    _spec("gen_simple_capacitor_charge_discharge", "simple", "SimpleCapacitorChargeDischarge", ("electrical",), "3-5", "Build a self-contained Modelica model of a capacitor charging and discharging through two resistive paths controlled by a switch-like block. Include capacitor voltage output."),
)

MEDIUM_SPECS: tuple[PromptSpec, ...] = (
    _spec("gen_medium_dc_motor_pi_speed", "medium", "MediumDCMotorPISpeed", ("electrical", "mechanical", "control"), "6-10", "Build a self-contained Modelica model of a DC motor speed control loop with a PI controller. Include the motor electrical side, rotational inertia/load, controller, reference input, and measured speed output."),
    _spec("gen_medium_two_room_thermal_control", "medium", "MediumTwoRoomThermalControl", ("thermal", "control"), "6-10", "Build a self-contained Modelica model with two thermal zones exchanging heat, one heater, and an on-off or PI controller maintaining the first zone near a setpoint. Include both room temperatures."),
    _spec("gen_medium_two_tank_level_control", "medium", "MediumTwoTankLevelControl", ("fluid", "control"), "6-10", "Build a self-contained Modelica model of a two-tank liquid level system with inflow, interconnection, outlet, and a simple controller regulating the first tank level. Include both tank levels."),
    _spec("gen_medium_two_inertia_gear_control", "medium", "MediumTwoInertiaGearControl", ("mechanical", "control"), "6-10", "Build a self-contained Modelica model of a two-inertia drivetrain with a gear ratio, torque actuator, and speed controller. Include motor-side and load-side speeds."),
    _spec("gen_medium_rlc_sensor_feedback", "medium", "MediumRLCSensorFeedback", ("electrical", "control"), "6-10", "Build a self-contained Modelica model of an RLC plant with sensor feedback and a controller acting on the source amplitude. Include a controlled output voltage signal."),
    _spec("gen_medium_pump_tank_pipe_loop", "medium", "MediumPumpTankPipeLoop", ("fluid",), "6-10", "Build a self-contained Modelica model of a pump, pipe, and tank loop with a controllable pump input and tank level output. Keep the hydraulic structure simple but physically consistent."),
    _spec("gen_medium_mass_spring_position_control", "medium", "MediumMassSpringPositionControl", ("mechanical", "control"), "6-10", "Build a self-contained Modelica model of a mass-spring-damper position servo with a reference position, controller, actuator force, and measured position output."),
    _spec("gen_medium_battery_load_converter", "medium", "MediumBatteryLoadConverter", ("electrical", "control"), "6-10", "Build a self-contained Modelica model of a simplified battery feeding a controllable DC load or converter stage with a voltage regulation loop. Include bus voltage and load current outputs."),
    _spec("gen_medium_heat_exchanger_valve", "medium", "MediumHeatExchangerValve", ("fluid", "thermal", "control"), "6-10", "Build a self-contained Modelica model of a simple fluid heat exchanger branch with a valve or flow control signal, thermal interaction, and outlet temperature output."),
    _spec("gen_medium_motor_thermal_protection", "medium", "MediumMotorThermalProtection", ("electrical", "mechanical", "thermal", "control"), "6-10", "Build a self-contained Modelica model of a motor drive with a simple thermal protection logic that reduces input when motor temperature is high. Include speed and temperature outputs."),
    _spec("gen_medium_boiler_tank_control", "medium", "MediumBoilerTankControl", ("thermal", "control"), "6-10", "Build a self-contained Modelica model of a heated water or thermal storage tank with a boiler/heater and simple temperature control. Include tank temperature output."),
    _spec("gen_medium_hydraulic_actuator_position", "medium", "MediumHydraulicActuatorPosition", ("fluid", "mechanical", "control"), "6-10", "Build a self-contained Modelica model of a simplified hydraulic actuator with position control. Keep the fluid network compact and expose actuator position output."),
)

COMPLEX_SPECS: tuple[PromptSpec, ...] = (
    _spec("gen_complex_liquid_cooling_loop", "complex", "ComplexLiquidCoolingLoop", ("fluid", "thermal", "control"), "10-16", "Build a self-contained Modelica model of a liquid cooling loop with pump, cold plate or heat source, radiator or cooler, reservoir, and a controller adjusting pump or fan command. Include coolant temperature and flow outputs."),
    _spec("gen_complex_building_hvac_zone", "complex", "ComplexBuildingHVACZone", ("fluid", "thermal", "control"), "10-16", "Build a self-contained Modelica model of a small HVAC subsystem serving one thermal zone, including fluid loop elements, heat exchange, and a controller maintaining zone temperature. Include zone temperature and supply temperature outputs."),
    _spec("gen_complex_hydronic_heating_loop", "complex", "ComplexHydronicHeatingLoop", ("fluid", "thermal", "control"), "10-16", "Build a self-contained Modelica model of a hydronic heating loop with pump, heater, distribution branch, thermal load, and loop temperature control. Include supply and return temperatures."),
    _spec("gen_complex_ev_thermal_management", "complex", "ComplexEVThermalManagement", ("electrical", "thermal", "fluid", "control"), "10-16", "Build a self-contained Modelica model of a simplified EV thermal-management subsystem coupling battery heat generation, coolant loop, heat rejection element, and supervisory control. Include battery temperature and coolant outlet temperature."),
    _spec("gen_complex_multi_tank_heat_exchange", "complex", "ComplexMultiTankHeatExchange", ("fluid", "thermal"), "10-16", "Build a self-contained Modelica model with multiple connected tanks, a recirculation loop, and a heat exchange path. Include key tank temperatures and liquid levels."),
    _spec("gen_complex_coupled_motor_drive_cooling", "complex", "ComplexCoupledMotorDriveCooling", ("electrical", "mechanical", "thermal", "fluid", "control"), "10-16", "Build a self-contained Modelica model of a motor drive coupled to a cooling loop and simple thermal derating control. Include motor speed, motor temperature, and coolant temperature outputs."),
    _spec("gen_complex_chilled_water_distribution", "complex", "ComplexChilledWaterDistribution", ("fluid", "thermal", "control"), "10-16", "Build a self-contained Modelica model of a chilled water distribution subsystem with pump, cooling source, load branch, bypass or valve logic, and temperature control. Include supply and return temperatures."),
    _spec("gen_complex_battery_pack_cooling_control", "complex", "ComplexBatteryPackCoolingControl", ("thermal", "fluid", "control"), "10-16", "Build a self-contained Modelica model of a battery pack thermal mass connected to a coolant loop with controlled flow or fan actuation. Include pack temperature and coolant outlet temperature."),
    _spec("gen_complex_heat_pump_buffer_tank_loop", "complex", "ComplexHeatPumpBufferTankLoop", ("fluid", "thermal", "control"), "10-16", "Build a self-contained Modelica model of a heat-pump-like thermal source connected to a buffer tank and controlled distribution loop. Include tank temperature and loop outlet temperature."),
    _spec("gen_complex_solar_thermal_storage_loop", "complex", "ComplexSolarThermalStorageLoop", ("thermal", "fluid", "control"), "10-16", "Build a self-contained Modelica model of a solar thermal collection and storage loop with circulation control and storage temperature output. Keep the model compact but multi-domain."),
    _spec("gen_complex_air_handling_unit_loop", "complex", "ComplexAirHandlingUnitLoop", ("fluid", "thermal", "control"), "10-16", "Build a self-contained Modelica model of a simplified air-handling or conditioned-flow loop with heat exchange and control over delivered temperature. Include supply temperature and zone temperature outputs."),
    _spec("gen_complex_boiler_radiator_return_loop", "complex", "ComplexBoilerRadiatorReturnLoop", ("fluid", "thermal", "control"), "10-16", "Build a self-contained Modelica model of a boiler-radiator-return loop with pump, radiator branch, thermal room load, and simple supply-temperature control. Include room temperature and return temperature outputs."),
)


def frozen_prompt_specs() -> dict[str, dict[str, list[dict]]]:
    tiers = {
        "simple": SIMPLE_SPECS,
        "medium": MEDIUM_SPECS,
        "complex": COMPLEX_SPECS,
    }
    payload: dict[str, dict[str, list[dict]]] = {}
    for tier, rows in tiers.items():
        active = [spec.to_dict(role="active", ordinal=idx + 1) for idx, spec in enumerate(rows[:10])]
        reserve = [spec.to_dict(role="reserve", ordinal=idx + 11) for idx, spec in enumerate(rows[10:])]
        payload[tier] = {"active_tasks": active, "reserve_tasks": reserve}
    return payload


def render_generation_prompt(task: dict) -> str:
    return (
        "You are generating a Modelica model from a natural language specification.\n"
        "Return ONLY a JSON object with keys: model_name, modelica_code, rationale.\n"
        "Constraints:\n"
        "- Output exactly one self-contained Modelica model.\n"
        f"- The model name must be exactly: {norm(task.get('model_name'))}\n"
        f"- Use only: {norm(task.get('allowed_library_scope'))}\n"
        "- Do not use package wrappers, partial classes, replaceable classes, or markdown fences.\n"
        "- Keep the design compact and simulation-oriented.\n"
        f"- Expected component count band: {norm(task.get('expected_component_count_band'))}\n"
        f"- Expected domain tags: {json.dumps(task.get('expected_domain_tags') or [], ensure_ascii=True)}\n"
        "Natural language specification:\n"
        f"{norm(task.get('natural_language_spec'))}\n"
    )


def _fallback_modelica_code(text: str, model_name: str) -> str:
    raw = str(text or "")
    if f"model {model_name}" in raw and f"end {model_name};" in raw:
        start = raw.find(f"model {model_name}")
        end = raw.rfind(f"end {model_name};")
        if start >= 0 and end >= start:
            return raw[start : end + len(f"end {model_name};")].strip()
    return ""


def generate_modelica_draft(task: dict, *, requested_backend: str = "") -> dict:
    adapter, config = resolve_provider_adapter(requested_backend)
    prompt = render_generation_prompt(task)
    response_text, error = send_with_budget(adapter, prompt, config)
    if error:
        raise RuntimeError(error)
    payload = extract_json_object(response_text, strict=False)
    model_name = norm(payload.get("model_name")) or norm(task.get("model_name"))
    modelica_code = norm(payload.get("modelica_code"))
    if not modelica_code:
        modelica_code = _fallback_modelica_code(response_text, model_name)
    return {
        "provider_name": str(config.provider_name or adapter.provider_name),
        "model": str(config.model or ""),
        "response_text": response_text,
        "model_name": model_name,
        "modelica_code": modelica_code,
        "rationale": norm(payload.get("rationale")),
        "generation_success": bool(modelica_code),
    }


def _runtime_protocol(*, evaluation_label: str, planner_backend_name: str, max_rounds: int) -> dict:
    return {
        "protocol_version": "v0.3.17_generation_distribution_calibration",
        "evaluation_label": str(evaluation_label or "").strip(),
        "profile_id": "repair-executor",
        "max_rounds": int(max_rounds),
        "timeout_sec": 600,
        "simulate_stop_time": 10.0,
        "simulate_intervals": 500,
        "planner_backend": str(planner_backend_name or ""),
        "experience_replay": "off",
        "planner_experience_injection": "off",
        "experience_source": "",
        "enabled_policy_flags": {
            "source_restore_allowed": False,
            "deterministic_rules_enabled": True,
            "replay_enabled": False,
            "planner_injection_enabled": False,
            "behavioral_contract_required": False,
            "allow_baseline_single_sweep": True,
            "allow_new_multistep_policy": False,
            "allow_branch_switch_replan_policy": False,
            "allow_same_branch_continuity_policy": False,
        },
    }


def run_generated_model_live(
    *,
    task_id: str,
    modelica_code: str,
    result_dir: str | Path,
    evaluation_label: str,
    max_rounds: int,
    declared_failure_type: str = "simulate_error",
    expected_stage: str = "simulate",
    timeout_sec: int = 600,
) -> dict:
    backend = planner_backend()
    out_root = Path(result_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gf_v0317_") as td:
        tmp = Path(td)
        source_mo = tmp / "source_model.mo"
        mutated_mo = tmp / "mutated_model.mo"
        source_mo.write_text(str(modelica_code or ""), encoding="utf-8")
        mutated_mo.write_text(str(modelica_code or ""), encoding="utf-8")
        result_path = out_root / f"{task_id}_result.json"
        runtime_context = AgentModelicaRuntimeContext.create(
            task_id=task_id,
            run_id=f"{task_id}_{evaluation_label}",
            arm_kind="gateforge",
            profile_id="repair-executor",
            artifact_root=out_root,
            source_model_path=source_mo,
            mutated_model_path=mutated_mo,
            result_path=result_path,
            declared_failure_type=str(declared_failure_type or "simulate_error"),
            expected_stage=str(expected_stage or "simulate"),
            max_rounds=int(max_rounds),
            simulate_stop_time=10.0,
            simulate_intervals=500,
            timeout_sec=int(timeout_sec),
            planner_backend=backend,
            omc_backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
            protocol_version="v0.3.17_generation_distribution_calibration",
            enabled_policy_flags=_runtime_protocol(
                evaluation_label=evaluation_label,
                planner_backend_name=backend,
                max_rounds=max_rounds,
            )["enabled_policy_flags"],
        )
        runtime_context.baseline_measurement_protocol = _runtime_protocol(
            evaluation_label=evaluation_label,
            planner_backend_name=backend,
            max_rounds=max_rounds,
        )
        runtime_context.write_json(out_root / f"{task_id}_runtime_context.json")
        cmd = runtime_context.executor_command()
        cmd += [
            "--experience-replay",
            "off",
            "--planner-experience-injection",
            "off",
            "--planner-experience-max-tokens",
            "0",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(REPO_ROOT),
            env={**os.environ, "PATH": "/usr/local/bin:" + os.environ.get("PATH", "")},
        )
    return {
        "result_json_path": str(result_path.resolve()),
        "return_code": int(proc.returncode),
        "stdout_snippet": str(proc.stdout or "")[:300],
        "stderr_snippet": str(proc.stderr or "")[:300],
        "detail": load_json(result_path),
        "planner_backend": backend,
        "max_rounds": int(max_rounds),
    }


def extract_snapshot(detail: dict, *, attempt_index: int = 0) -> dict:
    attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
    attempt = attempts[attempt_index] if 0 <= attempt_index < len(attempts) and isinstance(attempts[attempt_index], dict) else {}
    diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
    stage_subtype = norm(diagnostic.get("dominant_stage_subtype") or detail.get("dominant_stage_subtype"))
    error_subtype = norm(diagnostic.get("error_subtype"))
    observed_failure_type = norm(attempt.get("observed_failure_type") or detail.get("failure_type"))
    reason = norm(attempt.get("reason") or diagnostic.get("reason"))
    cluster = residual_signal_cluster(
        dominant_stage_subtype=stage_subtype,
        error_subtype=error_subtype,
        observed_failure_type=observed_failure_type,
        reason=reason,
    )
    return {
        "round_idx": int(attempt.get("round") or attempt_index + 1),
        "dominant_stage_subtype": stage_subtype,
        "error_subtype": error_subtype,
        "observed_failure_type": observed_failure_type,
        "reason": reason,
        "residual_signal_cluster": cluster,
        "declared_failure_type_canonical": norm(diagnostic.get("declared_failure_type_canonical") or diagnostic.get("declared_failure_type")),
        "expected_stage": norm(diagnostic.get("stage") or detail.get("expected_stage")),
        "suggested_actions": diagnostic.get("suggested_actions") if isinstance(diagnostic.get("suggested_actions"), list) else [],
    }


def classify_library_resolution_status(detail: dict) -> str:
    joined = "\n".join(
        [
            norm(detail.get("error_message")),
            norm(detail.get("compile_error")),
            norm(detail.get("simulate_error_message")),
            norm(detail.get("stderr_snippet")),
        ]
    ).lower()
    for attempt in detail.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        joined += "\n" + norm(attempt.get("reason")).lower()
        diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
        joined += "\n" + norm(diagnostic.get("reason")).lower()
    hints = (
        "class not found",
        "component not found",
        "package not found",
        "lookup of",
        "was not found in scope",
        "error occurred while flattening model",
        "imported package",
        "failed to load package",
        "unable to find class",
    )
    if any(token in joined for token in hints):
        return "unresolved"
    return "resolved"


def failure_type_for_second_run(snapshot: dict) -> tuple[str, str]:
    canonical = norm(snapshot.get("declared_failure_type_canonical"))
    stage = norm(snapshot.get("dominant_stage_subtype"))
    expected_stage = norm(snapshot.get("expected_stage"))
    if canonical in {"parse_error", "model_check_error", "simulate_error"}:
        return canonical, expected_stage or ("simulate" if canonical == "simulate_error" else "check")
    if stage.startswith("stage_1_"):
        return "parse_error", "check"
    if stage.startswith("stage_2_") or stage.startswith("stage_3_"):
        return "model_check_error", "check"
    return "simulate_error", "simulate"


def classify_actionability(snapshot: dict) -> str:
    stage = norm(snapshot.get("dominant_stage_subtype"))
    error_subtype = norm(snapshot.get("error_subtype"))
    reason = norm(snapshot.get("reason")).lower()
    suggested_actions = snapshot.get("suggested_actions") if isinstance(snapshot.get("suggested_actions"), list) else []
    if stage.startswith("stage_0_"):
        return "high_actionability"
    if stage.startswith("stage_1_"):
        return "high_actionability"
    if stage.startswith("stage_2_"):
        if "class not found" in reason or "not found in scope" in reason or "undefined" in reason:
            return "medium_actionability"
        return "low_actionability"
    if stage.startswith("stage_3_"):
        return "low_actionability"
    if stage.startswith("stage_4_"):
        return "medium_actionability"
    if stage.startswith("stage_5_"):
        if error_subtype in {"division_by_zero", "assertion_failure"} or len(suggested_actions) >= 2:
            return "high_actionability"
        return "medium_actionability"
    return "low_actionability"


def first_repair_action_type(detail: dict) -> str:
    attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
    if not attempts or not isinstance(attempts[0], dict):
        return "no_repair_action"
    first = attempts[0]
    for field_name, value in first.items():
        if not isinstance(value, dict):
            continue
        if not bool(value.get("applied")):
            continue
        action_type = action_type_from_row(
            attempt_field=norm(field_name),
            action_key=norm(value.get("action_key")),
            rule_id=norm(value.get("rule_id")),
        )
        if action_type:
            return action_type
    if bool(first.get("llm_plan_used")):
        return "llm_repair"
    return "no_repair_action"


def key_tuple(snapshot: dict) -> tuple[str, str]:
    return (norm(snapshot.get("dominant_stage_subtype")), norm(snapshot.get("residual_signal_cluster")))
