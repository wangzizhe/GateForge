from __future__ import annotations

import json
from pathlib import Path

from .agent_modelica_diagnostic_ir_v0 import build_diagnostic_ir_v0
from .agent_modelica_omc_workspace_v1 import run_omc_script_docker, temporary_workspace
from .agent_modelica_v0_3_19_common import DOCKER_IMAGE, replacement_audit
from .agent_modelica_v0_3_20_common import load_json, norm, write_json, write_text
from .agent_modelica_v0_3_21_common import now_utc
from .agent_modelica_v0_3_25_common import build_v0325_source_specs


SCHEMA_PREFIX = "agent_modelica_v0_3_29"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TRIAGE_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_29_viability_triage_current"
DEFAULT_ENTRY_SPEC_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_29_entry_family_spec_current"
DEFAULT_ENTRY_TASKSET_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_29_entry_taskset_current"
DEFAULT_PATCH_CONTRACT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_29_patch_contract_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_29_closeout_current"

LOCAL_CONNECTION_TARGET_STAGE = "check"
LOCAL_CONNECTION_TARGET_SUBTYPE = "underconstrained_system"
MEDIUM_REDECLARE_TARGET_STAGE = "check"
MEDIUM_REDECLARE_TARGET_SUBTYPE = "compile_failure_unknown"

SIMPLE_TWO_INERTIA_SHAFT_TEXT = "\n".join(
    [
        "model SimpleTwoInertiaShaft",
        "  Modelica.Mechanics.Rotational.Sources.Torque torque(useSupport = false);",
        "  Modelica.Mechanics.Rotational.Components.Inertia inertia1(J = 1.0);",
        "  Modelica.Mechanics.Rotational.Components.SpringDamper shaft(c = 1000, d = 10);",
        "  Modelica.Mechanics.Rotational.Components.Inertia inertia2(J = 1.0);",
        "  Modelica.Blocks.Interfaces.RealOutput w1 = inertia1.w;",
        "  Modelica.Blocks.Interfaces.RealOutput w2 = inertia2.w;",
        "equation",
        "  connect(torque.flange, inertia1.flange_a);",
        "  connect(inertia1.flange_b, shaft.flange_a);",
        "  connect(shaft.flange_b, inertia2.flange_a);",
        "end SimpleTwoInertiaShaft;",
    ]
)

MEDIUM_SOURCE_SPECS = [
    {
        "source_id": "medium_port_pipe_tank",
        "complexity_tier": "medium",
        "model_name": "PortPipeTank",
        "source_model_text": "\n".join(
            [
                "model PortPipeTank",
                "  replaceable package Medium = Modelica.Media.Water.ConstantPropertyLiquidWater;",
                "  inner Modelica.Fluid.System system;",
                "  Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                "  Modelica.Fluid.Pipes.StaticPipe pipe(redeclare package Medium = Medium, length=10, diameter=0.1);",
                "  Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=2, height=5, nPorts=1);",
                "  Modelica.Fluid.Interfaces.FluidPort_a port_a(redeclare package Medium = Medium);",
                "  Modelica.Fluid.Interfaces.FluidPort_b port_b(redeclare package Medium = Medium);",
                "equation",
                "  connect(ambient.ports[1], pipe.port_a);",
                "  connect(pipe.port_b, tank.ports[1]);",
                "  connect(port_a, ambient.ports[1]);",
                "  connect(tank.ports[1], port_b);",
                "end PortPipeTank;",
            ]
        ),
    },
    {
        "source_id": "medium_port_pipe_volume",
        "complexity_tier": "medium",
        "model_name": "PortPipeVolume",
        "source_model_text": "\n".join(
            [
                "model PortPipeVolume",
                "  replaceable package Medium = Modelica.Media.Water.ConstantPropertyLiquidWater;",
                "  inner Modelica.Fluid.System system;",
                "  Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                "  Modelica.Fluid.Pipes.StaticPipe pipe(redeclare package Medium = Medium, length=10, diameter=0.1);",
                "  Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=1);",
                "  Modelica.Fluid.Interfaces.FluidPort_a port_a(redeclare package Medium = Medium);",
                "  Modelica.Fluid.Interfaces.FluidPort_b port_b(redeclare package Medium = Medium);",
                "equation",
                "  connect(ambient.ports[1], pipe.port_a);",
                "  connect(pipe.port_b, volume.ports[1]);",
                "  connect(port_a, ambient.ports[1]);",
                "  connect(volume.ports[1], port_b);",
                "end PortPipeVolume;",
            ]
        ),
    },
    {
        "source_id": "medium_boundary_pipe_volume_sink",
        "complexity_tier": "medium",
        "model_name": "BoundaryPipeVolumeSink",
        "source_model_text": "\n".join(
            [
                "model BoundaryPipeVolumeSink",
                "  replaceable package Medium = Modelica.Media.Water.ConstantPropertyLiquidWater;",
                "  inner Modelica.Fluid.System system;",
                "  Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=102000, T=293.15, nPorts=1);",
                "  Modelica.Fluid.Pipes.StaticPipe pipe(redeclare package Medium = Medium, length=5, diameter=0.1);",
                "  Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=2);",
                "  Modelica.Fluid.Sources.Boundary_pT sink(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                "equation",
                "  connect(source.ports[1], pipe.port_a);",
                "  connect(pipe.port_b, volume.ports[1]);",
                "  connect(volume.ports[2], sink.ports[1]);",
                "end BoundaryPipeVolumeSink;",
            ]
        ),
    },
]

_V0325_SOURCE_MAP = {norm(row.get("source_id")): row for row in build_v0325_source_specs()}


def _local_connection_source_text(source_id: str) -> tuple[str, str]:
    if norm(source_id) == "gen_simple_two_inertia_shaft":
        return "SimpleTwoInertiaShaft", SIMPLE_TWO_INERTIA_SHAFT_TEXT
    row = _V0325_SOURCE_MAP.get(norm(source_id)) or {}
    return norm(row.get("model_name")), norm(row.get("source_model_text"))


LOCAL_CONNECTION_PATTERN_SPECS = [
    {
        "pattern_id": "two_inertia_missing_reference",
        "source_id": "gen_simple_two_inertia_shaft",
        "complexity_tier": "simple",
        "model_name": "SimpleTwoInertiaShaft",
        "mutation_kind": "generated_source_as_is",
        "injection_replacements": [],
        "allowed_patch_types": ["insert_component_declaration", "add_connect_statement"],
        "topology_intent_heavy": True,
    },
    {
        "pattern_id": "simple_force_missing_edge",
        "source_id": "simple_sine_driven_mass",
        "complexity_tier": "simple",
        "mutation_kind": "single_omitted_neighbor_connection",
        "injection_replacements": [("  connect(force.flange, mass.flange_a);\n", "")],
        "allowed_patch_types": ["add_connect_statement"],
        "topology_intent_heavy": False,
    },
    {
        "pattern_id": "medium_possensor_missing_edge",
        "source_id": "medium_mass_spring_position_control",
        "complexity_tier": "medium",
        "mutation_kind": "single_omitted_neighbor_connection",
        "injection_replacements": [("  connect(posSensor.flange, mass.flange_a);\n", "")],
        "allowed_patch_types": ["add_connect_statement"],
        "topology_intent_heavy": False,
    },
]

MEDIUM_FALLBACK_PATTERN_SPECS = [
    {
        "pattern_id": "tank_missing_medium_redeclare",
        "source_id": "medium_port_pipe_tank",
        "complexity_tier": "medium",
        "patch_type": "insert_redeclare_package_medium",
        "mutation_kind": "single_component_medium_redeclare_omission",
        "injection_replacements": [
            (
                "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=2, height=5, nPorts=1);",
                "Modelica.Fluid.Vessels.OpenTank tank(crossArea=2, height=5, nPorts=1);",
            )
        ],
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Vessels.OpenTank tank(crossArea=2, height=5, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=2, height=5, nPorts=1);",
            }
        ],
    },
    {
        "pattern_id": "ambient_missing_medium_redeclare",
        "source_id": "medium_port_pipe_tank",
        "complexity_tier": "medium",
        "patch_type": "insert_redeclare_package_medium",
        "mutation_kind": "single_component_medium_redeclare_omission",
        "injection_replacements": [
            (
                "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
            )
        ],
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
            }
        ],
    },
    {
        "pattern_id": "volume_missing_medium_redeclare",
        "source_id": "medium_boundary_pipe_volume_sink",
        "complexity_tier": "medium",
        "patch_type": "insert_redeclare_package_medium",
        "mutation_kind": "single_component_medium_redeclare_omission",
        "injection_replacements": [
            (
                "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=2);",
                "Modelica.Fluid.Vessels.ClosedVolume volume(V=0.5, nPorts=2);",
            )
        ],
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Vessels.ClosedVolume volume(V=0.5, nPorts=2);",
                "replacement_text": "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=2);",
            }
        ],
    },
]

MEDIUM_ENTRY_SINGLE_SPECS = [
    {
        "task_id": "v0329_single_port_pipe_tank_missing_tank",
        "source_id": "medium_port_pipe_tank",
        "complexity_tier": "medium",
        "patch_type": "insert_redeclare_package_medium",
        "wrong_target": "tank.redeclare_package_Medium_missing",
        "correct_target": "tank.redeclare package Medium = Medium",
        "injection_replacements": [
            (
                "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=2, height=5, nPorts=1);",
                "Modelica.Fluid.Vessels.OpenTank tank(crossArea=2, height=5, nPorts=1);",
            )
        ],
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Vessels.OpenTank tank(crossArea=2, height=5, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=2, height=5, nPorts=1);",
            }
        ],
    },
    {
        "task_id": "v0329_single_port_pipe_tank_missing_ambient",
        "source_id": "medium_port_pipe_tank",
        "complexity_tier": "medium",
        "patch_type": "insert_redeclare_package_medium",
        "wrong_target": "ambient.redeclare_package_Medium_missing",
        "correct_target": "ambient.redeclare package Medium = Medium",
        "injection_replacements": [
            (
                "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
            )
        ],
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
            }
        ],
    },
    {
        "task_id": "v0329_single_port_pipe_volume_missing_volume",
        "source_id": "medium_port_pipe_volume",
        "complexity_tier": "medium",
        "patch_type": "insert_redeclare_package_medium",
        "wrong_target": "volume.redeclare_package_Medium_missing",
        "correct_target": "volume.redeclare package Medium = Medium",
        "injection_replacements": [
            (
                "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=1);",
                "Modelica.Fluid.Vessels.ClosedVolume volume(V=0.5, nPorts=1);",
            )
        ],
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Vessels.ClosedVolume volume(V=0.5, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=1);",
            }
        ],
    },
    {
        "task_id": "v0329_single_port_pipe_volume_missing_ambient",
        "source_id": "medium_port_pipe_volume",
        "complexity_tier": "medium",
        "patch_type": "insert_redeclare_package_medium",
        "wrong_target": "ambient.redeclare_package_Medium_missing",
        "correct_target": "ambient.redeclare package Medium = Medium",
        "injection_replacements": [
            (
                "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
            )
        ],
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
            }
        ],
    },
    {
        "task_id": "v0329_single_boundary_pipe_volume_sink_missing_volume",
        "source_id": "medium_boundary_pipe_volume_sink",
        "complexity_tier": "medium",
        "patch_type": "insert_redeclare_package_medium",
        "wrong_target": "volume.redeclare_package_Medium_missing",
        "correct_target": "volume.redeclare package Medium = Medium",
        "injection_replacements": [
            (
                "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=2);",
                "Modelica.Fluid.Vessels.ClosedVolume volume(V=0.5, nPorts=2);",
            )
        ],
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Vessels.ClosedVolume volume(V=0.5, nPorts=2);",
                "replacement_text": "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=2);",
            }
        ],
    },
    {
        "task_id": "v0329_single_boundary_pipe_volume_sink_missing_source",
        "source_id": "medium_boundary_pipe_volume_sink",
        "complexity_tier": "medium",
        "patch_type": "insert_redeclare_package_medium",
        "wrong_target": "source.redeclare_package_Medium_missing",
        "correct_target": "source.redeclare package Medium = Medium",
        "injection_replacements": [
            (
                "Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=102000, T=293.15, nPorts=1);",
                "Modelica.Fluid.Sources.Boundary_pT source(p=102000, T=293.15, nPorts=1);",
            )
        ],
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Sources.Boundary_pT source(p=102000, T=293.15, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=102000, T=293.15, nPorts=1);",
            }
        ],
    },
    {
        "task_id": "v0329_single_boundary_pipe_volume_sink_missing_sink",
        "source_id": "medium_boundary_pipe_volume_sink",
        "complexity_tier": "medium",
        "patch_type": "insert_redeclare_package_medium",
        "wrong_target": "sink.redeclare_package_Medium_missing",
        "correct_target": "sink.redeclare package Medium = Medium",
        "injection_replacements": [
            (
                "Modelica.Fluid.Sources.Boundary_pT sink(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                "Modelica.Fluid.Sources.Boundary_pT sink(p=101325, T=293.15, nPorts=1);",
            )
        ],
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Sources.Boundary_pT sink(p=101325, T=293.15, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Sources.Boundary_pT sink(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
            }
        ],
    },
]

MEDIUM_ENTRY_DUAL_SPECS = [
    {
        "task_id": "v0329_dual_port_pipe_tank_ambient_then_tank",
        "source_id": "medium_port_pipe_tank",
        "complexity_tier": "medium",
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
            },
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Vessels.OpenTank tank(crossArea=2, height=5, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=2, height=5, nPorts=1);",
            },
        ],
        "injection_replacements": [
            (
                "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
            ),
            (
                "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=2, height=5, nPorts=1);",
                "Modelica.Fluid.Vessels.OpenTank tank(crossArea=2, height=5, nPorts=1);",
            ),
        ],
    },
    {
        "task_id": "v0329_dual_port_pipe_tank_tank_then_ambient",
        "source_id": "medium_port_pipe_tank",
        "complexity_tier": "medium",
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Vessels.OpenTank tank(crossArea=2, height=5, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=2, height=5, nPorts=1);",
            },
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
            },
        ],
        "injection_replacements": [
            (
                "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
            ),
            (
                "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=2, height=5, nPorts=1);",
                "Modelica.Fluid.Vessels.OpenTank tank(crossArea=2, height=5, nPorts=1);",
            ),
        ],
    },
    {
        "task_id": "v0329_dual_port_pipe_volume_ambient_then_volume",
        "source_id": "medium_port_pipe_volume",
        "complexity_tier": "medium",
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
            },
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Vessels.ClosedVolume volume(V=0.5, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=1);",
            },
        ],
        "injection_replacements": [
            (
                "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
            ),
            (
                "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=1);",
                "Modelica.Fluid.Vessels.ClosedVolume volume(V=0.5, nPorts=1);",
            ),
        ],
    },
    {
        "task_id": "v0329_dual_boundary_pipe_volume_sink_source_then_volume",
        "source_id": "medium_boundary_pipe_volume_sink",
        "complexity_tier": "medium",
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Sources.Boundary_pT source(p=102000, T=293.15, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=102000, T=293.15, nPorts=1);",
            },
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Vessels.ClosedVolume volume(V=0.5, nPorts=2);",
                "replacement_text": "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=2);",
            },
        ],
        "injection_replacements": [
            (
                "Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=102000, T=293.15, nPorts=1);",
                "Modelica.Fluid.Sources.Boundary_pT source(p=102000, T=293.15, nPorts=1);",
            ),
            (
                "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=2);",
                "Modelica.Fluid.Vessels.ClosedVolume volume(V=0.5, nPorts=2);",
            ),
        ],
    },
    {
        "task_id": "v0329_dual_boundary_pipe_volume_sink_volume_then_sink",
        "source_id": "medium_boundary_pipe_volume_sink",
        "complexity_tier": "medium",
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Vessels.ClosedVolume volume(V=0.5, nPorts=2);",
                "replacement_text": "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=2);",
            },
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": "Modelica.Fluid.Sources.Boundary_pT sink(p=101325, T=293.15, nPorts=1);",
                "replacement_text": "Modelica.Fluid.Sources.Boundary_pT sink(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
            },
        ],
        "injection_replacements": [
            (
                "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=2);",
                "Modelica.Fluid.Vessels.ClosedVolume volume(V=0.5, nPorts=2);",
            ),
            (
                "Modelica.Fluid.Sources.Boundary_pT sink(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                "Modelica.Fluid.Sources.Boundary_pT sink(p=101325, T=293.15, nPorts=1);",
            ),
        ],
    },
]


def source_row_for(source_id: str) -> dict:
    if norm(source_id) in {norm(row.get("source_id")) for row in MEDIUM_SOURCE_SPECS}:
        for row in MEDIUM_SOURCE_SPECS:
            if norm(row.get("source_id")) == norm(source_id):
                return dict(row)
    model_name, source_model_text = _local_connection_source_text(source_id)
    return {
        "source_id": norm(source_id),
        "complexity_tier": "simple",
        "model_name": model_name,
        "source_model_text": source_model_text,
    }


def build_mutated_text(source_model_text: str, replacements: list[tuple[str, str]]) -> tuple[str, dict]:
    return replacement_audit(norm(source_model_text), [(str(a), str(b)) for a, b in replacements])


def apply_repair_step(model_text: str, step: dict) -> tuple[str, dict]:
    current = norm(model_text)
    match_text = norm(step.get("match_text"))
    replacement_text = norm(step.get("replacement_text"))
    if not match_text:
        return current, {"applied": False, "reason": "missing_match_text"}
    if match_text not in current:
        return current, {"applied": False, "reason": "match_text_not_found"}
    updated = current.replace(match_text, replacement_text, 1)
    return updated, {
        "applied": updated != current,
        "reason": "applied" if updated != current else "unchanged",
        "patch_type": norm(step.get("patch_type")),
    }


def run_dry_run(model_name: str, model_text: str, *, timeout_sec: int = 120) -> dict:
    script = "\n".join(
        [
            "loadModel(Modelica);",
            'loadFile("model.mo");',
            f"checkModel({model_name});",
            "getErrorString();",
            "",
        ]
    )
    with temporary_workspace("v0329_dry_run_") as td:
        target = Path(td) / "model.mo"
        target.write_text(norm(model_text), encoding="utf-8")
        rc, output = run_omc_script_docker(
            script_text=script,
            timeout_sec=timeout_sec,
            cwd=td,
            image=DOCKER_IMAGE,
        )
    check_model_pass = "completed successfully" in str(output or "") and "Error:" not in str(output or "")
    diagnostic = build_diagnostic_ir_v0(
        output=str(output or ""),
        check_model_pass=bool(check_model_pass),
        simulate_pass=True,
        expected_stage="check",
        declared_failure_type="simulate_error",
        declared_context_hints={},
    )
    return {
        "return_code": int(rc),
        "check_model_pass": bool(check_model_pass),
        "output_excerpt": norm(output)[:1200],
        "error_type": norm(diagnostic.get("error_type")),
        "error_subtype": norm(diagnostic.get("error_subtype")),
        "stage": norm(diagnostic.get("stage")),
        "observed_phase": norm(diagnostic.get("observed_phase")),
        "reason": norm(diagnostic.get("reason")),
    }


def local_connection_target_hit(result: dict) -> bool:
    return (
        norm(result.get("error_type")) == "model_check_error"
        and norm(result.get("stage")) == LOCAL_CONNECTION_TARGET_STAGE
        and norm(result.get("error_subtype")) == LOCAL_CONNECTION_TARGET_SUBTYPE
    )


def medium_redeclare_target_hit(result: dict) -> bool:
    output_excerpt = norm(result.get("output_excerpt")).lower()
    return (
        norm(result.get("error_type")) == "model_check_error"
        and norm(result.get("stage")) == MEDIUM_REDECLARE_TARGET_STAGE
        and norm(result.get("error_subtype")) == MEDIUM_REDECLARE_TARGET_SUBTYPE
        and any(
            token in output_excerpt
            for token in (
                "medium.single",
                "medium.thermostates",
                "partial class medium",
                "redeclare",
            )
        )
    )


def fixture_local_connection_result(*, passes: bool) -> dict:
    return {
        "return_code": 1 if passes else 0,
        "check_model_pass": False if passes else True,
        "output_excerpt": "Fixture underconstrained_system result." if passes else "Fixture no-error result.",
        "error_type": "model_check_error" if passes else "none",
        "error_subtype": "underconstrained_system" if passes else "none",
        "stage": "check" if passes else "none",
        "observed_phase": "check" if passes else "none",
        "reason": "structural balance failed" if passes else "",
    }


def fixture_medium_redeclare_result(*, passes: bool) -> dict:
    return {
        "return_code": 1 if passes else 0,
        "check_model_pass": False if passes else True,
        "output_excerpt": "Fixture Medium.singleState compile_failure_unknown result." if passes else "Fixture no-error result.",
        "error_type": "model_check_error" if passes else "none",
        "error_subtype": "compile_failure_unknown" if passes else "none",
        "stage": "check" if passes else "none",
        "observed_phase": "check" if passes else "none",
        "reason": "model check failed" if passes else "",
    }


def dump_json_line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=True)


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_ENTRY_SPEC_OUT_DIR",
    "DEFAULT_ENTRY_TASKSET_OUT_DIR",
    "DEFAULT_PATCH_CONTRACT_OUT_DIR",
    "DEFAULT_TRIAGE_OUT_DIR",
    "DOCKER_IMAGE",
    "LOCAL_CONNECTION_PATTERN_SPECS",
    "LOCAL_CONNECTION_TARGET_SUBTYPE",
    "MEDIUM_ENTRY_DUAL_SPECS",
    "MEDIUM_ENTRY_SINGLE_SPECS",
    "MEDIUM_FALLBACK_PATTERN_SPECS",
    "MEDIUM_REDECLARE_TARGET_SUBTYPE",
    "MEDIUM_SOURCE_SPECS",
    "SCHEMA_PREFIX",
    "apply_repair_step",
    "build_mutated_text",
    "dump_json_line",
    "fixture_local_connection_result",
    "fixture_medium_redeclare_result",
    "load_json",
    "local_connection_target_hit",
    "medium_redeclare_target_hit",
    "norm",
    "now_utc",
    "run_dry_run",
    "source_row_for",
    "write_json",
    "write_text",
]
