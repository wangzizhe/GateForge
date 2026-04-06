from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_6_2_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_6_3"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_3_handoff_integrity_current"
)
DEFAULT_DECISION_INPUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_3_phase_decision_input_current"
)
DEFAULT_CANDIDATE_ADJUDICATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_3_candidate_adjudication_current"
)
DEFAULT_DECISION_BASIS_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_3_decision_basis_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_3_closeout_current"
)

DEFAULT_V062_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_2_closeout_current" / "summary.json"
)
DEFAULT_V062_PROFILE_STABILITY_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_2_profile_stability_current" / "summary.json"
)
DEFAULT_V062_LIVE_RUN_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_2_live_run_current" / "summary.json"
)

OPEN_WORLD_STABLE_COVERAGE_MIN = 50.0
OPEN_WORLD_SPILLOVER_MAX = 10.0
TARGETED_EXPANSION_BOUNDED_UNCOVERED_MIN = 15.0


__all__ = [
    "DEFAULT_CANDIDATE_ADJUDICATION_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DECISION_BASIS_OUT_DIR",
    "DEFAULT_DECISION_INPUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V062_CLOSEOUT_PATH",
    "DEFAULT_V062_LIVE_RUN_PATH",
    "DEFAULT_V062_PROFILE_STABILITY_PATH",
    "OPEN_WORLD_SPILLOVER_MAX",
    "OPEN_WORLD_STABLE_COVERAGE_MIN",
    "SCHEMA_PREFIX",
    "TARGETED_EXPANSION_BOUNDED_UNCOVERED_MIN",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
