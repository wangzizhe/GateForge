from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_7_1_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_7_5"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_5_handoff_integrity_current"
)
DEFAULT_GAP_REFINEMENT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_5_gap_refinement_current"
)
DEFAULT_REFINEMENT_ADJUDICATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_5_refinement_adjudication_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_5_closeout_current"
)

DEFAULT_V074_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_4_closeout_current" / "summary.json"
)
DEFAULT_V073_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_3_closeout_current" / "summary.json"
)

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_GAP_REFINEMENT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_REFINEMENT_ADJUDICATION_OUT_DIR",
    "DEFAULT_V073_CLOSEOUT_PATH",
    "DEFAULT_V074_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
