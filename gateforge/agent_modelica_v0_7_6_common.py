from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_7_1_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_7_6"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_6_handoff_integrity_current"
)
DEFAULT_LATE_PHASE_SUPPORT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_6_late_phase_support_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_6_closeout_current"
)

DEFAULT_V075_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_5_closeout_current" / "summary.json"
)
DEFAULT_V074_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_4_closeout_current" / "summary.json"
)

SUPPORTED_STABLE_COVERAGE_FLOOR = 40.0
CLOSEOUT_SUPPORT_GAP_MAX = 3.0
BOUNDED_UNCOVERED_SUBCRITICAL_MAX = 15.0

__all__ = [
    "BOUNDED_UNCOVERED_SUBCRITICAL_MAX",
    "CLOSEOUT_SUPPORT_GAP_MAX",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_LATE_PHASE_SUPPORT_OUT_DIR",
    "DEFAULT_V074_CLOSEOUT_PATH",
    "DEFAULT_V075_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "SUPPORTED_STABLE_COVERAGE_FLOOR",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
