from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_runtime_context_v1 import AgentModelicaRuntimeContext
from .agent_modelica_v0_3_17_common import extract_snapshot, planner_backend as resolve_live_planner_backend


SCHEMA_PREFIX = "agent_modelica_v0_3_19"
REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKER_IMAGE = os.environ.get("GATEFORGE_DOCKER_IMAGE", "openmodelica/openmodelica:v1.26.1-minimal")

DEFAULT_FAMILY_SPEC_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_19_family_spec_current"
DEFAULT_TASKSET_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_19_taskset_current"
DEFAULT_PREVIEW_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_19_preview_results_current"
DEFAULT_PREVIEW_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_19_preview_admission_current"
DEFAULT_LIVE_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_19_live_results_current"
DEFAULT_LIVE_EVIDENCE_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_19_live_evidence_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_19_closeout_current"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(value: object) -> str:
    return str(value or "").strip()


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


SOURCE_SPECS: list[dict] = [
    {
        "source_id": "simple_sine_driven_mass",
        "complexity_tier": "simple",
        "model_name": "ApiAlignSimpleSineDrivenMass",
        "source_model_text": "\n".join(
            [
                "model ApiAlignSimpleSineDrivenMass",
                "  Modelica.Mechanics.Translational.Components.Mass mass(m = 1.0, s(start = 0), v(start = 0));",
                "  Modelica.Mechanics.Translational.Components.Spring spring(c = 10.0, s_rel0 = 0);",
                "  Modelica.Mechanics.Translational.Components.Damper damper(d = 0.5);",
                "  Modelica.Mechanics.Translational.Sources.Force force;",
                "  Modelica.Blocks.Sources.Sine sine(amplitude = 5.0, f = 0.5, offset = 0.0);",
                "  Modelica.Mechanics.Translational.Components.Fixed fixed;",
                "  output Real pos = mass.s;",
                "  output Real vel = mass.v;",
                "equation",
                "  connect(fixed.flange, spring.flange_a);",
                "  connect(spring.flange_b, mass.flange_a);",
                "  connect(damper.flange_a, fixed.flange);",
                "  connect(damper.flange_b, mass.flange_a);",
                "  connect(sine.y, force.f);",
                "  connect(force.flange, mass.flange_a);",
                "end ApiAlignSimpleSineDrivenMass;",
            ]
        ),
        "variants": [
            {
                "variant_id": "same_component_class_param",
                "placement_kind": "same_component_dual_mismatch",
                "focal_component": "sine",
                "mutation_shape": "class_path_surface_mismatch+parameter_surface_mismatch",
                "replacements": [
                    ("Modelica.Blocks.Sources.Sine", "Modelica.Blocks.Source.Sine"),
                    ("f = 0.5", "freqHz = 0.5"),
                ],
                "expected_first_error_signature_hint": "Class Sine not found in package Source",
                "expected_second_error_signature_hint": "Modified element freqHz not found in class Sine",
            },
            {
                "variant_id": "same_component_param_param",
                "placement_kind": "same_component_dual_mismatch",
                "focal_component": "sine",
                "mutation_shape": "parameter_surface_mismatch+parameter_surface_mismatch",
                "replacements": [
                    ("amplitude = 5.0", "amp = 5.0"),
                    ("f = 0.5", "freqHz = 0.5"),
                ],
                "expected_first_error_signature_hint": "Modified element amp not found in class Sine",
                "expected_second_error_signature_hint": "Modified element freqHz not found in class Sine",
            },
        ],
    },
    {
        "source_id": "simple_thermal_heated_mass",
        "complexity_tier": "simple",
        "model_name": "ApiAlignSimpleThermalHeatedMass",
        "source_model_text": "\n".join(
            [
                "model ApiAlignSimpleThermalHeatedMass",
                "  Modelica.Thermal.HeatTransfer.Components.HeatCapacitor mass(C = 1000);",
                "  Modelica.Thermal.HeatTransfer.Components.ThermalResistor resistor(R = 0.5);",
                "  Modelica.Thermal.HeatTransfer.Sources.PrescribedHeatFlow heater;",
                "  Modelica.Thermal.HeatTransfer.Sources.FixedTemperature ambient(T = 293.15);",
                "  Modelica.Blocks.Sources.Constant Q_flow(k = 100);",
                "  output Real T_mass = mass.T;",
                "equation",
                "  connect(Q_flow.y, heater.Q_flow);",
                "  connect(heater.port, mass.port);",
                "  connect(mass.port, resistor.port_a);",
                "  connect(resistor.port_b, ambient.port);",
                "end ApiAlignSimpleThermalHeatedMass;",
            ]
        ),
        "variants": [
            {
                "variant_id": "same_component_class_param",
                "placement_kind": "same_component_dual_mismatch",
                "focal_component": "ambient",
                "mutation_shape": "class_path_surface_mismatch+parameter_surface_mismatch",
                "replacements": [
                    ("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "Modelica.Thermal.HeatTransfer.Components.FixedTemperature"),
                    ("T = 293.15", "temperature = 293.15"),
                ],
                "expected_first_error_signature_hint": "Class FixedTemperature not found in package Components",
                "expected_second_error_signature_hint": "Modified element temperature not found in class FixedTemperature",
            }
        ],
    },
    {
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "model_name": "ApiAlignMediumMassSpringPositionControl",
        "source_model_text": "\n".join(
            [
                "model ApiAlignMediumMassSpringPositionControl",
                "  Modelica.Blocks.Sources.Step reference(height = 1.0, startTime = 0.5, offset = 0.0);",
                "  Modelica.Blocks.Math.Feedback feedback;",
                "  Modelica.Blocks.Continuous.PI controller(k = 10.0, T = 0.2);",
                "  Modelica.Blocks.Math.Gain actuator(k = 20.0);",
                "  Modelica.Mechanics.Translational.Sources.Force force;",
                "  Modelica.Mechanics.Translational.Components.Mass mass(m = 1.0, s(start = 0), v(start = 0));",
                "  Modelica.Mechanics.Translational.Components.Spring spring(c = 50.0, s_rel0 = 0);",
                "  Modelica.Mechanics.Translational.Components.Damper damper(d = 2.0);",
                "  Modelica.Mechanics.Translational.Components.Fixed fixed;",
                "  Modelica.Mechanics.Translational.Sensors.PositionSensor posSensor;",
                "equation",
                "  connect(reference.y, feedback.u1);",
                "  connect(posSensor.s, feedback.u2);",
                "  connect(feedback.y, controller.u);",
                "  connect(controller.y, actuator.u);",
                "  connect(actuator.y, force.f);",
                "  connect(force.flange, mass.flange_a);",
                "  connect(spring.flange_a, fixed.flange);",
                "  connect(spring.flange_b, mass.flange_a);",
                "  connect(damper.flange_a, fixed.flange);",
                "  connect(damper.flange_b, mass.flange_a);",
                "  connect(posSensor.flange, mass.flange_a);",
                "end ApiAlignMediumMassSpringPositionControl;",
            ]
        ),
        "variants": [
            {
                "variant_id": "same_component_class_param",
                "placement_kind": "same_component_dual_mismatch",
                "focal_component": "reference",
                "mutation_shape": "class_path_surface_mismatch+parameter_surface_mismatch",
                "replacements": [
                    ("Modelica.Blocks.Sources.Step", "Modelica.Blocks.Source.Step"),
                    ("startTime = 0.5", "startT = 0.5"),
                ],
                "expected_first_error_signature_hint": "Class Step not found in package Source",
                "expected_second_error_signature_hint": "Modified element startT not found in class Step",
            },
            {
                "variant_id": "same_component_param_param",
                "placement_kind": "same_component_dual_mismatch",
                "focal_component": "reference",
                "mutation_shape": "parameter_surface_mismatch+parameter_surface_mismatch",
                "replacements": [
                    ("height = 1.0", "amplitude = 1.0"),
                    ("startTime = 0.5", "startT = 0.5"),
                ],
                "expected_first_error_signature_hint": "Modified element amplitude not found in class Step",
                "expected_second_error_signature_hint": "Modified element startT not found in class Step",
            },
        ],
    },
    {
        "source_id": "medium_thermal_control",
        "complexity_tier": "medium",
        "model_name": "ApiAlignMediumThermalControl",
        "source_model_text": "\n".join(
            [
                "model ApiAlignMediumThermalControl",
                "  Modelica.Blocks.Sources.Step reference(height = 5.0, startTime = 100.0, offset = 293.15);",
                "  Modelica.Blocks.Math.Feedback feedback;",
                "  Modelica.Blocks.Continuous.PI controller(k = 50.0, T = 20.0);",
                "  Modelica.Blocks.Math.Gain heaterGain(k = 1.0);",
                "  Modelica.Thermal.HeatTransfer.Sources.PrescribedHeatFlow heater;",
                "  Modelica.Thermal.HeatTransfer.Components.HeatCapacitor room(C = 10000.0, T(start = 293.15));",
                "  Modelica.Thermal.HeatTransfer.Components.ThermalResistor wall(R = 0.1);",
                "  Modelica.Thermal.HeatTransfer.Sources.FixedTemperature ambient(T = 293.15);",
                "  output Real roomTemperature = room.T;",
                "equation",
                "  feedback.u1 = reference.y;",
                "  feedback.u2 = room.T;",
                "  connect(feedback.y, controller.u);",
                "  connect(controller.y, heaterGain.u);",
                "  connect(heaterGain.y, heater.Q_flow);",
                "  connect(heater.port, room.port);",
                "  connect(room.port, wall.port_a);",
                "  connect(wall.port_b, ambient.port);",
                "end ApiAlignMediumThermalControl;",
            ]
        ),
        "variants": [
            {
                "variant_id": "same_component_class_param",
                "placement_kind": "same_component_dual_mismatch",
                "focal_component": "ambient",
                "mutation_shape": "class_path_surface_mismatch+parameter_surface_mismatch",
                "replacements": [
                    ("Modelica.Thermal.HeatTransfer.Sources.FixedTemperature", "Modelica.Thermal.HeatTransfer.Components.FixedTemperature"),
                    ("T = 293.15", "temperature = 293.15"),
                ],
                "expected_first_error_signature_hint": "Class FixedTemperature not found in package Components",
                "expected_second_error_signature_hint": "Modified element temperature not found in class FixedTemperature",
            }
        ],
    },
]


def build_source_specs() -> list[dict]:
    return [dict(row) for row in SOURCE_SPECS]


def replacement_audit(model_text: str, replacements: list[tuple[str, str]]) -> tuple[str, dict]:
    mutated = str(model_text or "")
    audits = []
    for old, new in replacements:
        idx = mutated.find(old)
        if idx < 0:
            return model_text, {
                "applied": False,
                "reason": "replacement_target_not_found",
                "failed_old": old,
            }
        mutated = mutated.replace(old, new, 1)
        audits.append({"old": old, "new": new, "offset": idx})
    return mutated, {
        "applied": True,
        "replacement_count": len(audits),
        "replacements": audits,
    }


def error_signature_from_text(text: str) -> str:
    content = norm(text)
    if not content:
        return ""
    match = re.search(r"Error:\s*(.+)", content)
    if match:
        return norm(match.group(1))
    quoted = re.findall(r"\"([^\"]*Error:[^\"]*)\"", content)
    if quoted:
        return norm(quoted[-1])
    line = next((line for line in content.splitlines() if "Error:" in line), "")
    return norm(line)


def error_signature_from_attempt(attempt: dict) -> str:
    if not isinstance(attempt, dict):
        return ""
    return error_signature_from_text(norm(attempt.get("log_excerpt")) or norm(attempt.get("reason")))


def _runtime_protocol(*, evaluation_label: str, max_rounds: int, planner_backend_name: str) -> dict:
    return {
        "protocol_version": "v0.3.19_stage2_api_alignment",
        "evaluation_label": evaluation_label,
        "profile_id": "repair-executor",
        "max_rounds": int(max_rounds),
        "timeout_sec": 600,
        "simulate_stop_time": 10.0,
        "simulate_intervals": 500,
        "planner_backend": planner_backend_name,
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


def run_synthetic_task_live(
    *,
    task: dict,
    result_dir: str | Path,
    evaluation_label: str,
    max_rounds: int,
    timeout_sec: int = 600,
) -> dict:
    backend = resolve_live_planner_backend()
    out_root = Path(result_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    task_id = norm(task.get("task_id"))
    with tempfile.TemporaryDirectory(prefix="gf_v0319_") as td:
        tmp = Path(td)
        source_mo = tmp / "source_model.mo"
        mutated_mo = tmp / "mutated_model.mo"
        source_mo.write_text(norm(task.get("source_model_text")), encoding="utf-8")
        mutated_mo.write_text(norm(task.get("mutated_model_text")), encoding="utf-8")
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
            declared_failure_type=str(task.get("declared_failure_type") or "model_check_error"),
            expected_stage=str(task.get("expected_stage") or "check"),
            max_rounds=int(max_rounds),
            simulate_stop_time=10.0,
            simulate_intervals=500,
            timeout_sec=int(timeout_sec),
            planner_backend=backend,
            omc_backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
            protocol_version="v0.3.19_stage2_api_alignment",
            enabled_policy_flags=_runtime_protocol(
                evaluation_label=evaluation_label,
                max_rounds=max_rounds,
                planner_backend_name=backend,
            )["enabled_policy_flags"],
        )
        runtime_context.baseline_measurement_protocol = _runtime_protocol(
            evaluation_label=evaluation_label,
            max_rounds=max_rounds,
            planner_backend_name=backend,
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
        "stdout_snippet": str(proc.stdout or "")[:400],
        "stderr_snippet": str(proc.stderr or "")[:400],
        "detail": load_json(result_path),
        "planner_backend": backend,
        "max_rounds": int(max_rounds),
    }


def second_snapshot(detail: dict) -> dict:
    attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
    if len(attempts) >= 2 and isinstance(attempts[1], dict):
        return extract_snapshot(detail, attempt_index=1)
    if str(detail.get("executor_status") or "").upper() == "PASS":
        return {
            "round_idx": 2,
            "dominant_stage_subtype": "stage_0_none",
            "error_subtype": "none",
            "observed_failure_type": "none",
            "reason": "",
            "residual_signal_cluster": "resolved",
        }
    carried = extract_snapshot(detail, attempt_index=0)
    carried["round_idx"] = 2
    return carried
