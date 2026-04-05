from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_4_6_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_5_0"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WIDENED_SPEC_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_0_widened_spec_current"
DEFAULT_CANDIDATE_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_0_candidate_pack_current"
DEFAULT_DISPATCH_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_0_dispatch_cleanliness_current"
DEFAULT_BOUNDARY_GATE_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_0_boundary_gate_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_0_closeout_current"

DEFAULT_V043_REAL_SLICE_FREEZE_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_3_real_slice_freeze_current" / "summary.json"
DEFAULT_V046_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_6_closeout_current" / "summary.json"

MINIMUM_CASE_DELTA_VS_V04_TARGETED = 6
MINIMUM_QUALITATIVE_CASE_COUNT = 4
MINIMUM_QUALITATIVE_CASE_SHARE_PCT = 20
MINIMUM_DISTINCT_QUALITATIVE_BUCKET_COUNT = 1
MINIMUM_OVERLAP_CASE_REQUIREMENT = 6

PROMOTED_ATTRIBUTION_AMBIGUITY_RATE_PCT_MAX = 20
PROMOTED_OVERLAP_CASE_COUNT_MIN = 6
DEGRADED_ATTRIBUTION_AMBIGUITY_RATE_PCT_MAX = 30
DEGRADED_OVERLAP_CASE_COUNT_MIN = 4


def norm(value: object) -> str:
    return str(value or "").strip().lower()


def classify_real_case(task_id: str, family_id: str) -> dict[str, str]:
    tid = norm(task_id)
    fam = norm(family_id)

    if fam == "component_api_alignment":
        return {
            "slice_class": "already-covered",
            "qualitative_bucket": "none",
            "reason": "Falls inside the already-authority-supported API-alignment slice.",
        }

    if fam == "local_interface_alignment":
        if any(token in tid for token in ("ev_thermal_management", "building_hvac_zone", "motor_thermal_protection", "two_tank_level_control")):
            return {
                "slice_class": "boundary-adjacent",
                "qualitative_bucket": "cross_domain_interface_pressure",
                "reason": "Remains locally interpretable but pushes interface repair into higher-complexity cross-domain pressure.",
            }
        return {
            "slice_class": "already-covered",
            "qualitative_bucket": "none",
            "reason": "Falls inside the currently declared local-interface slice.",
        }

    if fam == "medium_redeclare_alignment":
        if any(token in tid for token in ("hydronic", "chilled_water", "heat_pump_buffer", "solar_thermal_storage", "pipe")):
            return {
                "slice_class": "undeclared-but-bounded-candidate",
                "qualitative_bucket": "fluid_network_medium_surface_pressure",
                "reason": "Keeps a bounded local medium-redeclare surface while moving beyond the previously targeted narrower real slice.",
            }
        return {
            "slice_class": "boundary-adjacent",
            "qualitative_bucket": "medium_cluster_boundary_pressure",
            "reason": "Still tied to medium-redeclare repair but closer to uncovered local fluid boundary behavior.",
        }

    return {
        "slice_class": "",
        "qualitative_bucket": "",
        "reason": "Unclassified case.",
    }


__all__ = [
    "DEFAULT_BOUNDARY_GATE_OUT_DIR",
    "DEFAULT_CANDIDATE_PACK_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DISPATCH_AUDIT_OUT_DIR",
    "DEFAULT_V043_REAL_SLICE_FREEZE_PATH",
    "DEFAULT_V046_CLOSEOUT_PATH",
    "DEFAULT_WIDENED_SPEC_OUT_DIR",
    "DEGRADED_ATTRIBUTION_AMBIGUITY_RATE_PCT_MAX",
    "DEGRADED_OVERLAP_CASE_COUNT_MIN",
    "MINIMUM_CASE_DELTA_VS_V04_TARGETED",
    "MINIMUM_DISTINCT_QUALITATIVE_BUCKET_COUNT",
    "MINIMUM_OVERLAP_CASE_REQUIREMENT",
    "MINIMUM_QUALITATIVE_CASE_COUNT",
    "MINIMUM_QUALITATIVE_CASE_SHARE_PCT",
    "PROMOTED_ATTRIBUTION_AMBIGUITY_RATE_PCT_MAX",
    "PROMOTED_OVERLAP_CASE_COUNT_MIN",
    "SCHEMA_PREFIX",
    "classify_real_case",
    "load_json",
    "norm",
    "now_utc",
    "write_json",
    "write_text",
]
