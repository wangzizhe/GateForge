from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_3_20_common import load_json, norm, write_json, write_text
from .agent_modelica_v0_3_21_common import now_utc
from .agent_modelica_v0_3_29_common import (
    apply_repair_step,
    build_mutated_text,
    fixture_medium_redeclare_result,
    medium_redeclare_target_hit,
    run_dry_run,
)
from .agent_modelica_v0_3_30_common import (
    apply_medium_redeclare_discovery_patch,
    build_medium_candidate_rhs_symbols,
    fixture_dry_run_result,
    parse_canonical_rhs_from_repair_step,
    rank_medium_rhs_candidates,
)


SCHEMA_PREFIX = "agent_modelica_v0_3_31"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MANIFEST_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_31_coverage_manifest_current"
DEFAULT_SURFACE_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_31_surface_export_audit_current"
DEFAULT_FIRST_FIX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_31_first_fix_evidence_current"
DEFAULT_DUAL_RECHECK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_31_dual_recheck_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_31_closeout_current"

DEFAULT_V0330_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_30_closeout_current" / "summary.json"
DEFAULT_V0330_DISCOVERY_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_30_discovery_evidence_current" / "summary.json"

ALLOWED_PATCH_TYPES = [
    "insert_redeclare_package_medium",
    "replace_redeclare_clause",
    "replace_medium_package_symbol",
]


def _without_redeclare(declaration: str) -> str:
    value = norm(declaration)
    value = value.replace("(redeclare package Medium = Medium, ", "(", 1)
    value = value.replace("(redeclare package Medium = Medium);", "();", 1)
    return value


def _source_row(
    *,
    source_id: str,
    model_name: str,
    source_model_text: str,
    component_variants: list[dict],
) -> dict:
    return {
        "source_id": source_id,
        "complexity_tier": "medium",
        "model_name": model_name,
        "source_model_text": source_model_text,
        "component_variants": component_variants,
    }


def build_v0331_source_specs() -> list[dict]:
    return [
        _source_row(
            source_id="medium_port_pipe_tank",
            model_name="PortPipeTank",
            source_model_text="\n".join(
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
            component_variants=[
                {
                    "component_name": "ambient",
                    "subtype": "boundary_like",
                    "declaration": "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                },
                {
                    "component_name": "pipe",
                    "subtype": "pipe_or_local_fluid_interface_like",
                    "declaration": "Modelica.Fluid.Pipes.StaticPipe pipe(redeclare package Medium = Medium, length=10, diameter=0.1);",
                },
                {
                    "component_name": "tank",
                    "subtype": "vessel_or_volume_like",
                    "declaration": "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=2, height=5, nPorts=1);",
                },
                {
                    "component_name": "port_a",
                    "subtype": "pipe_or_local_fluid_interface_like",
                    "declaration": "Modelica.Fluid.Interfaces.FluidPort_a port_a(redeclare package Medium = Medium);",
                },
                {
                    "component_name": "port_b",
                    "subtype": "pipe_or_local_fluid_interface_like",
                    "declaration": "Modelica.Fluid.Interfaces.FluidPort_b port_b(redeclare package Medium = Medium);",
                },
            ],
        ),
        _source_row(
            source_id="medium_port_pipe_volume",
            model_name="PortPipeVolume",
            source_model_text="\n".join(
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
            component_variants=[
                {
                    "component_name": "ambient",
                    "subtype": "boundary_like",
                    "declaration": "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                },
                {
                    "component_name": "pipe",
                    "subtype": "pipe_or_local_fluid_interface_like",
                    "declaration": "Modelica.Fluid.Pipes.StaticPipe pipe(redeclare package Medium = Medium, length=10, diameter=0.1);",
                },
                {
                    "component_name": "volume",
                    "subtype": "vessel_or_volume_like",
                    "declaration": "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=1);",
                },
                {
                    "component_name": "port_a",
                    "subtype": "pipe_or_local_fluid_interface_like",
                    "declaration": "Modelica.Fluid.Interfaces.FluidPort_a port_a(redeclare package Medium = Medium);",
                },
                {
                    "component_name": "port_b",
                    "subtype": "pipe_or_local_fluid_interface_like",
                    "declaration": "Modelica.Fluid.Interfaces.FluidPort_b port_b(redeclare package Medium = Medium);",
                },
            ],
        ),
        _source_row(
            source_id="medium_boundary_pipe_volume_sink",
            model_name="BoundaryPipeVolumeSink",
            source_model_text="\n".join(
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
            component_variants=[
                {
                    "component_name": "source",
                    "subtype": "boundary_like",
                    "declaration": "Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=102000, T=293.15, nPorts=1);",
                },
                {
                    "component_name": "pipe",
                    "subtype": "pipe_or_local_fluid_interface_like",
                    "declaration": "Modelica.Fluid.Pipes.StaticPipe pipe(redeclare package Medium = Medium, length=5, diameter=0.1);",
                },
                {
                    "component_name": "volume",
                    "subtype": "vessel_or_volume_like",
                    "declaration": "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.5, nPorts=2);",
                },
                {
                    "component_name": "sink",
                    "subtype": "boundary_like",
                    "declaration": "Modelica.Fluid.Sources.Boundary_pT sink(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                },
            ],
        ),
        _source_row(
            source_id="medium_boundary_pipe_tank_sink",
            model_name="BoundaryPipeTankSink",
            source_model_text="\n".join(
                [
                    "model BoundaryPipeTankSink",
                    "  replaceable package Medium = Modelica.Media.Water.ConstantPropertyLiquidWater;",
                    "  inner Modelica.Fluid.System system;",
                    "  Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=102000, T=293.15, nPorts=1);",
                    "  Modelica.Fluid.Pipes.StaticPipe pipe(redeclare package Medium = Medium, length=6, diameter=0.08);",
                    "  Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=1.5, height=4, nPorts=2);",
                    "  Modelica.Fluid.Sources.Boundary_pT sink(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                    "equation",
                    "  connect(source.ports[1], pipe.port_a);",
                    "  connect(pipe.port_b, tank.ports[1]);",
                    "  connect(tank.ports[2], sink.ports[1]);",
                    "end BoundaryPipeTankSink;",
                ]
            ),
            component_variants=[
                {
                    "component_name": "source",
                    "subtype": "boundary_like",
                    "declaration": "Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=102000, T=293.15, nPorts=1);",
                },
                {
                    "component_name": "pipe",
                    "subtype": "pipe_or_local_fluid_interface_like",
                    "declaration": "Modelica.Fluid.Pipes.StaticPipe pipe(redeclare package Medium = Medium, length=6, diameter=0.08);",
                },
                {
                    "component_name": "tank",
                    "subtype": "vessel_or_volume_like",
                    "declaration": "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=1.5, height=4, nPorts=2);",
                },
                {
                    "component_name": "sink",
                    "subtype": "boundary_like",
                    "declaration": "Modelica.Fluid.Sources.Boundary_pT sink(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                },
            ],
        ),
        _source_row(
            source_id="medium_source_pipe_tank_ports",
            model_name="SourcePipeTankPorts",
            source_model_text="\n".join(
                [
                    "model SourcePipeTankPorts",
                    "  replaceable package Medium = Modelica.Media.Water.ConstantPropertyLiquidWater;",
                    "  inner Modelica.Fluid.System system;",
                    "  Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=101800, T=293.15, nPorts=1);",
                    "  Modelica.Fluid.Pipes.StaticPipe pipe(redeclare package Medium = Medium, length=7, diameter=0.08);",
                    "  Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=1.8, height=3, nPorts=1);",
                    "  Modelica.Fluid.Interfaces.FluidPort_a port_a(redeclare package Medium = Medium);",
                    "  Modelica.Fluid.Interfaces.FluidPort_b port_b(redeclare package Medium = Medium);",
                    "equation",
                    "  connect(source.ports[1], pipe.port_a);",
                    "  connect(pipe.port_b, tank.ports[1]);",
                    "  connect(port_a, source.ports[1]);",
                    "  connect(tank.ports[1], port_b);",
                    "end SourcePipeTankPorts;",
                ]
            ),
            component_variants=[
                {
                    "component_name": "source",
                    "subtype": "boundary_like",
                    "declaration": "Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=101800, T=293.15, nPorts=1);",
                },
                {
                    "component_name": "pipe",
                    "subtype": "pipe_or_local_fluid_interface_like",
                    "declaration": "Modelica.Fluid.Pipes.StaticPipe pipe(redeclare package Medium = Medium, length=7, diameter=0.08);",
                },
                {
                    "component_name": "tank",
                    "subtype": "vessel_or_volume_like",
                    "declaration": "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=1.8, height=3, nPorts=1);",
                },
                {
                    "component_name": "port_a",
                    "subtype": "pipe_or_local_fluid_interface_like",
                    "declaration": "Modelica.Fluid.Interfaces.FluidPort_a port_a(redeclare package Medium = Medium);",
                },
                {
                    "component_name": "port_b",
                    "subtype": "pipe_or_local_fluid_interface_like",
                    "declaration": "Modelica.Fluid.Interfaces.FluidPort_b port_b(redeclare package Medium = Medium);",
                },
            ],
        ),
        _source_row(
            source_id="medium_boundary_volume_sink_series",
            model_name="BoundaryVolumeSinkSeries",
            source_model_text="\n".join(
                [
                    "model BoundaryVolumeSinkSeries",
                    "  replaceable package Medium = Modelica.Media.Water.ConstantPropertyLiquidWater;",
                    "  inner Modelica.Fluid.System system;",
                    "  Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=101900, T=293.15, nPorts=1);",
                    "  Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.75, nPorts=2);",
                    "  Modelica.Fluid.Sources.Boundary_pT sink(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                    "equation",
                    "  connect(source.ports[1], volume.ports[1]);",
                    "  connect(volume.ports[2], sink.ports[1]);",
                    "end BoundaryVolumeSinkSeries;",
                ]
            ),
            component_variants=[
                {
                    "component_name": "source",
                    "subtype": "boundary_like",
                    "declaration": "Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=101900, T=293.15, nPorts=1);",
                },
                {
                    "component_name": "volume",
                    "subtype": "vessel_or_volume_like",
                    "declaration": "Modelica.Fluid.Vessels.ClosedVolume volume(redeclare package Medium = Medium, V=0.75, nPorts=2);",
                },
                {
                    "component_name": "sink",
                    "subtype": "boundary_like",
                    "declaration": "Modelica.Fluid.Sources.Boundary_pT sink(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                },
            ],
        ),
        _source_row(
            source_id="medium_boundary_tank_sink_series",
            model_name="BoundaryTankSinkSeries",
            source_model_text="\n".join(
                [
                    "model BoundaryTankSinkSeries",
                    "  replaceable package Medium = Modelica.Media.Water.ConstantPropertyLiquidWater;",
                    "  inner Modelica.Fluid.System system;",
                    "  Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=101900, T=293.15, nPorts=1);",
                    "  Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=1.2, height=3.5, nPorts=2);",
                    "  Modelica.Fluid.Sources.Boundary_pT sink(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                    "equation",
                    "  connect(source.ports[1], tank.ports[1]);",
                    "  connect(tank.ports[2], sink.ports[1]);",
                    "end BoundaryTankSinkSeries;",
                ]
            ),
            component_variants=[
                {
                    "component_name": "source",
                    "subtype": "boundary_like",
                    "declaration": "Modelica.Fluid.Sources.Boundary_pT source(redeclare package Medium = Medium, p=101900, T=293.15, nPorts=1);",
                },
                {
                    "component_name": "tank",
                    "subtype": "vessel_or_volume_like",
                    "declaration": "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=1.2, height=3.5, nPorts=2);",
                },
                {
                    "component_name": "sink",
                    "subtype": "boundary_like",
                    "declaration": "Modelica.Fluid.Sources.Boundary_pT sink(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                },
            ],
        ),
    ]


def _source_map() -> dict[str, dict]:
    return {norm(row.get("source_id")): row for row in build_v0331_source_specs()}


def source_row_for(source_id: str) -> dict:
    return dict(_source_map().get(norm(source_id)) or {})


def _component_variant(source_id: str, component_name: str) -> dict:
    source = source_row_for(source_id)
    for row in list(source.get("component_variants") or []):
        if norm(row.get("component_name")) == norm(component_name):
            payload = dict(row)
            payload["without_redeclare"] = _without_redeclare(norm(row.get("declaration")))
            return payload
    return {}


def _single_spec(source_id: str, component_name: str) -> dict:
    source = source_row_for(source_id)
    variant = _component_variant(source_id, component_name)
    declaration = norm(variant.get("declaration"))
    without = norm(variant.get("without_redeclare"))
    task_id = f"v0331_single_{source_id}_missing_{component_name}"
    return {
        "task_id": task_id,
        "source_id": source_id,
        "complexity_tier": norm(source.get("complexity_tier")) or "medium",
        "component_name": component_name,
        "component_subtype": norm(variant.get("subtype")),
        "patch_type": "insert_redeclare_package_medium",
        "wrong_target": f"{component_name}.redeclare_package_Medium_missing",
        "correct_target": f"{component_name}.redeclare package Medium = Medium",
        "injection_replacements": [(declaration, without)],
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": without,
                "replacement_text": declaration,
            }
        ],
    }


def _dual_spec(source_id: str, first_component: str, second_component: str) -> dict:
    source = source_row_for(source_id)
    first = _component_variant(source_id, first_component)
    second = _component_variant(source_id, second_component)
    task_id = f"v0331_dual_{source_id}_{first_component}_then_{second_component}"
    return {
        "task_id": task_id,
        "source_id": source_id,
        "complexity_tier": norm(source.get("complexity_tier")) or "medium",
        "component_name": f"{first_component}->{second_component}",
        "component_subtype": norm(first.get("subtype")),
        "repair_steps": [
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": norm(first.get("without_redeclare")),
                "replacement_text": norm(first.get("declaration")),
            },
            {
                "patch_type": "insert_redeclare_package_medium",
                "match_text": norm(second.get("without_redeclare")),
                "replacement_text": norm(second.get("declaration")),
            },
        ],
        "injection_replacements": [
            (norm(first.get("declaration")), norm(first.get("without_redeclare"))),
            (norm(second.get("declaration")), norm(second.get("without_redeclare"))),
        ],
    }


SINGLE_TASK_BLUEPRINTS = [
    ("medium_port_pipe_tank", "ambient"),
    ("medium_port_pipe_tank", "pipe"),
    ("medium_port_pipe_tank", "tank"),
    ("medium_port_pipe_tank", "port_a"),
    ("medium_port_pipe_tank", "port_b"),
    ("medium_port_pipe_volume", "ambient"),
    ("medium_port_pipe_volume", "pipe"),
    ("medium_port_pipe_volume", "volume"),
    ("medium_port_pipe_volume", "port_a"),
    ("medium_port_pipe_volume", "port_b"),
    ("medium_boundary_pipe_volume_sink", "source"),
    ("medium_boundary_pipe_volume_sink", "pipe"),
    ("medium_boundary_pipe_volume_sink", "volume"),
    ("medium_boundary_pipe_volume_sink", "sink"),
    ("medium_boundary_pipe_tank_sink", "source"),
    ("medium_boundary_pipe_tank_sink", "pipe"),
    ("medium_boundary_pipe_tank_sink", "tank"),
    ("medium_boundary_pipe_tank_sink", "sink"),
    ("medium_source_pipe_tank_ports", "source"),
    ("medium_source_pipe_tank_ports", "pipe"),
    ("medium_source_pipe_tank_ports", "tank"),
    ("medium_source_pipe_tank_ports", "port_a"),
    ("medium_source_pipe_tank_ports", "port_b"),
    ("medium_boundary_volume_sink_series", "source"),
    ("medium_boundary_volume_sink_series", "volume"),
    ("medium_boundary_volume_sink_series", "sink"),
    ("medium_boundary_tank_sink_series", "source"),
    ("medium_boundary_tank_sink_series", "tank"),
    ("medium_boundary_tank_sink_series", "sink"),
]

DUAL_TASK_BLUEPRINTS = [
    ("medium_port_pipe_tank", "ambient", "tank"),
    ("medium_port_pipe_tank", "tank", "ambient"),
    ("medium_port_pipe_tank", "pipe", "tank"),
    ("medium_port_pipe_tank", "port_a", "port_b"),
    ("medium_port_pipe_volume", "ambient", "volume"),
    ("medium_port_pipe_volume", "volume", "ambient"),
    ("medium_port_pipe_volume", "pipe", "volume"),
    ("medium_port_pipe_volume", "port_a", "port_b"),
    ("medium_boundary_pipe_volume_sink", "source", "volume"),
    ("medium_boundary_pipe_volume_sink", "volume", "sink"),
    ("medium_boundary_pipe_volume_sink", "pipe", "sink"),
    ("medium_boundary_pipe_tank_sink", "source", "tank"),
    ("medium_boundary_pipe_tank_sink", "tank", "sink"),
    ("medium_source_pipe_tank_ports", "source", "tank"),
    ("medium_source_pipe_tank_ports", "tank", "port_b"),
    ("medium_source_pipe_tank_ports", "port_a", "port_b"),
    ("medium_boundary_volume_sink_series", "source", "volume"),
    ("medium_boundary_volume_sink_series", "volume", "sink"),
    ("medium_boundary_tank_sink_series", "source", "tank"),
    ("medium_boundary_tank_sink_series", "tank", "sink"),
]


def build_v0331_single_specs() -> list[dict]:
    return [_single_spec(source_id, component_name) for source_id, component_name in SINGLE_TASK_BLUEPRINTS]


def build_v0331_dual_specs() -> list[dict]:
    return [_dual_spec(source_id, first_component, second_component) for source_id, first_component, second_component in DUAL_TASK_BLUEPRINTS]


__all__ = [
    "ALLOWED_PATCH_TYPES",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_FIRST_FIX_OUT_DIR",
    "DEFAULT_MANIFEST_OUT_DIR",
    "DEFAULT_SURFACE_AUDIT_OUT_DIR",
    "DEFAULT_DUAL_RECHECK_OUT_DIR",
    "DEFAULT_V0330_CLOSEOUT_PATH",
    "DEFAULT_V0330_DISCOVERY_PATH",
    "SCHEMA_PREFIX",
    "apply_medium_redeclare_discovery_patch",
    "apply_repair_step",
    "build_medium_candidate_rhs_symbols",
    "build_mutated_text",
    "build_v0331_dual_specs",
    "build_v0331_single_specs",
    "build_v0331_source_specs",
    "fixture_dry_run_result",
    "fixture_medium_redeclare_result",
    "load_json",
    "medium_redeclare_target_hit",
    "norm",
    "now_utc",
    "parse_canonical_rhs_from_repair_step",
    "rank_medium_rhs_candidates",
    "run_dry_run",
    "source_row_for",
    "write_json",
    "write_text",
]
