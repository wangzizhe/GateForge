from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_7_1_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_7_2"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_2_handoff_integrity_current"
)
DEFAULT_PROFILE_EXTENSION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_2_profile_extension_current"
)
DEFAULT_LIVE_RUN_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_2_live_run_current"
)
DEFAULT_PROFILE_STABILITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_2_profile_stability_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_2_closeout_current"
)

DEFAULT_V071_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_1_closeout_current" / "summary.json"
)
DEFAULT_V070_SUBSTRATE_PATH = (
    REPO_ROOT
    / "artifacts"
    / "agent_modelica_v0_7_0_open_world_adjacent_substrate_current"
    / "summary.json"
)

LEGACY_BUCKET_MAPPING_STABLE_MIN = 75.0
LEGACY_BUCKET_MAPPING_PARTIAL_MIN = 70.0
SPILLOVER_STABLE_MAX = 25.0
SPILLOVER_INVALID_MAX = 40.0
STABLE_COVERAGE_STABLE_MIN = 35.0


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_LIVE_RUN_OUT_DIR",
    "DEFAULT_PROFILE_EXTENSION_OUT_DIR",
    "DEFAULT_PROFILE_STABILITY_OUT_DIR",
    "DEFAULT_V070_SUBSTRATE_PATH",
    "DEFAULT_V071_CLOSEOUT_PATH",
    "LEGACY_BUCKET_MAPPING_PARTIAL_MIN",
    "LEGACY_BUCKET_MAPPING_STABLE_MIN",
    "SCHEMA_PREFIX",
    "SPILLOVER_INVALID_MAX",
    "SPILLOVER_STABLE_MAX",
    "STABLE_COVERAGE_STABLE_MIN",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
