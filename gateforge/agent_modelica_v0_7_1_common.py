from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_7_0_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_7_1"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_1_handoff_integrity_current"
)
DEFAULT_LIVE_RUN_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_1_live_run_current"
)
DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_1_profile_classification_current"
)
DEFAULT_PROFILE_ADJUDICATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_1_profile_adjudication_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_1_closeout_current"
)

DEFAULT_V070_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_0_closeout_current" / "summary.json"
)
DEFAULT_V070_SUBSTRATE_PATH = (
    REPO_ROOT
    / "artifacts"
    / "agent_modelica_v0_7_0_open_world_adjacent_substrate_current"
    / "summary.json"
)

LEGACY_BUCKET_MAPPING_READY_MIN = 70.0
SPILLOVER_READY_MAX = 25.0
SPILLOVER_INVALID_MAX = 40.0
STABLE_COVERAGE_READY_MIN = 40.0


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_LIVE_RUN_OUT_DIR",
    "DEFAULT_PROFILE_ADJUDICATION_OUT_DIR",
    "DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR",
    "DEFAULT_V070_CLOSEOUT_PATH",
    "DEFAULT_V070_SUBSTRATE_PATH",
    "LEGACY_BUCKET_MAPPING_READY_MIN",
    "SCHEMA_PREFIX",
    "SPILLOVER_INVALID_MAX",
    "SPILLOVER_READY_MAX",
    "STABLE_COVERAGE_READY_MIN",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
