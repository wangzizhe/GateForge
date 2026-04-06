from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_7_1_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_7_3"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_3_handoff_integrity_current"
)
DEFAULT_DECISION_INPUT_TABLE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_3_decision_input_table_current"
)
DEFAULT_DECISION_ADJUDICATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_3_decision_adjudication_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_7_3_closeout_current"

DEFAULT_V071_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_1_closeout_current" / "summary.json"
)
DEFAULT_V072_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_2_closeout_current" / "summary.json"
)

LEGACY_BUCKET_MAPPING_READY_MIN = 80.0
LEGACY_BUCKET_MAPPING_PARTIAL_MIN = 75.0
SPILLOVER_READY_MAX = 20.0
SPILLOVER_PARTIAL_MAX = 25.0
STABLE_COVERAGE_READY_MIN = 35.0

OPEN_WORLD_SUPPORTED_FLOOR = {
    "stable_coverage_share_pct": 40.0,
    "spillover_share_pct": 20.0,
    "legacy_bucket_mapping_rate_pct": 80.0,
}

OPEN_WORLD_PARTIAL_FLOOR = {
    "stable_coverage_share_pct": 35.0,
    "spillover_share_pct": 25.0,
    "legacy_bucket_mapping_rate_pct": 75.0,
}

FALLBACK_TO_TARGETED_EXPANSION_FLOOR = {
    "bounded_uncovered_subtype_candidate_share_pct": 15.0,
}

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DECISION_ADJUDICATION_OUT_DIR",
    "DEFAULT_DECISION_INPUT_TABLE_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V071_CLOSEOUT_PATH",
    "DEFAULT_V072_CLOSEOUT_PATH",
    "FALLBACK_TO_TARGETED_EXPANSION_FLOOR",
    "LEGACY_BUCKET_MAPPING_PARTIAL_MIN",
    "LEGACY_BUCKET_MAPPING_READY_MIN",
    "OPEN_WORLD_PARTIAL_FLOOR",
    "OPEN_WORLD_SUPPORTED_FLOOR",
    "SCHEMA_PREFIX",
    "SPILLOVER_PARTIAL_MAX",
    "SPILLOVER_READY_MAX",
    "STABLE_COVERAGE_READY_MIN",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
