from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_7_1_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_7_7"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PHASE_LEDGER_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_7_phase_ledger_current"
)
DEFAULT_STOP_CONDITION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_7_stop_condition_current"
)
DEFAULT_MEANING_SYNTHESIS_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_7_meaning_synthesis_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_7_closeout_current"
)

DEFAULT_V070_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_0_closeout_current" / "summary.json"
)
DEFAULT_V071_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_1_closeout_current" / "summary.json"
)
DEFAULT_V072_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_2_closeout_current" / "summary.json"
)
DEFAULT_V073_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_3_closeout_current" / "summary.json"
)
DEFAULT_V074_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_4_closeout_current" / "summary.json"
)
DEFAULT_V075_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_5_closeout_current" / "summary.json"
)
DEFAULT_V076_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_6_closeout_current" / "summary.json"
)

LEGACY_TAXONOMY_DOMINANT_FLOOR = 70.0

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_MEANING_SYNTHESIS_OUT_DIR",
    "DEFAULT_PHASE_LEDGER_OUT_DIR",
    "DEFAULT_STOP_CONDITION_OUT_DIR",
    "DEFAULT_V070_CLOSEOUT_PATH",
    "DEFAULT_V071_CLOSEOUT_PATH",
    "DEFAULT_V072_CLOSEOUT_PATH",
    "DEFAULT_V073_CLOSEOUT_PATH",
    "DEFAULT_V074_CLOSEOUT_PATH",
    "DEFAULT_V075_CLOSEOUT_PATH",
    "DEFAULT_V076_CLOSEOUT_PATH",
    "LEGACY_TAXONOMY_DOMINANT_FLOOR",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
