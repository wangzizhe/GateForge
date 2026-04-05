from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_4_2_common import (
    DEFAULT_V0317_GENERATION_CENSUS_PATH,
    FAMILY_ORDER,
    STAGE2_DOMINANT_STAGE_SUBTYPE,
    STAGE2_ERROR_SUBTYPE,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_PREFIX = "agent_modelica_v0_4_3"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REAL_SLICE_FREEZE_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_3_real_slice_freeze_current"
DEFAULT_REAL_BACKCHECK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_3_real_backcheck_current"
DEFAULT_DISPATCH_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_3_dispatch_audit_current"
DEFAULT_V0_4_4_HANDOFF_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_3_v0_4_4_handoff_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_3_closeout_current"

DEFAULT_V042_REAL_BACKCHECK_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_2_real_backcheck_current" / "summary.json"
DEFAULT_V042_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_2_closeout_current" / "summary.json"


def _family_from_task_id(task_id: str) -> str:
    value = norm(task_id)
    if any(token in value for token in ("liquid_cooling", "hydronic", "chilled_water", "heat_pump_buffer", "solar_thermal_storage", "multi_tank_heat_exchange")):
        return "medium_redeclare_alignment"
    if any(token in value for token in ("two_room_thermal_control", "two_tank_level_control", "sensor_feedback", "motor_thermal_protection", "building_hvac_zone", "ev_thermal_management")):
        return "local_interface_alignment"
    if any(token in value for token in ("rc_lowpass", "thermal_heated_mass", "sine_driven_mass", "dc_motor_pi_speed", "mass_spring_position_control", "battery_load_converter")):
        return "component_api_alignment"
    return ""


def widened_real_candidates(generation_census: dict) -> list[dict]:
    rows = generation_census.get("rows") if isinstance(generation_census.get("rows"), list) else []
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        first_failure = row.get("first_failure") if isinstance(row.get("first_failure"), dict) else {}
        if norm(first_failure.get("dominant_stage_subtype")) != STAGE2_DOMINANT_STAGE_SUBTYPE:
            continue
        if norm(first_failure.get("error_subtype")) != STAGE2_ERROR_SUBTYPE:
            continue
        family_id = _family_from_task_id(str(row.get("task_id") or ""))
        if not family_id:
            continue
        out.append(
            {
                "task_id": row.get("task_id"),
                "family_id": family_id,
                "complexity_tier": row.get("complexity_tier"),
                "natural_language_spec": row.get("natural_language_spec"),
                "model_name": row.get("model_name"),
                "first_failure": first_failure,
                "family_target_bucket": f"{STAGE2_DOMINANT_STAGE_SUBTYPE}|{STAGE2_ERROR_SUBTYPE}",
            }
        )
    return out


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DISPATCH_AUDIT_OUT_DIR",
    "DEFAULT_REAL_BACKCHECK_OUT_DIR",
    "DEFAULT_REAL_SLICE_FREEZE_OUT_DIR",
    "DEFAULT_V0_4_4_HANDOFF_OUT_DIR",
    "DEFAULT_V0317_GENERATION_CENSUS_PATH",
    "DEFAULT_V042_CLOSEOUT_PATH",
    "DEFAULT_V042_REAL_BACKCHECK_PATH",
    "FAMILY_ORDER",
    "SCHEMA_PREFIX",
    "STAGE2_DOMINANT_STAGE_SUBTYPE",
    "STAGE2_ERROR_SUBTYPE",
    "load_json",
    "norm",
    "now_utc",
    "widened_real_candidates",
    "write_json",
    "write_text",
]
