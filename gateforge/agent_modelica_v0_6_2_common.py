from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_6_1_common import LEGACY_BUCKETS, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_6_2"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_2_handoff_integrity_current"
)
DEFAULT_AUTHORITY_SLICE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_2_authority_slice_current"
)
DEFAULT_LIVE_RUN_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_2_live_run_current"
)
DEFAULT_PROFILE_STABILITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_2_profile_stability_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_2_closeout_current"
)

DEFAULT_V061_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_1_closeout_current" / "summary.json"
)
DEFAULT_V061_PROFILE_ADJUDICATION_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_1_profile_adjudication_current" / "summary.json"
)
DEFAULT_V061_PROFILE_CLASSIFICATION_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_1_profile_classification_current" / "summary.json"
)
DEFAULT_V060_SUBSTRATE_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_0_representative_substrate_current" / "summary.json"
)

LEGACY_BUCKET_MAPPING_READY_MIN = 80.0
LEGACY_BUCKET_MAPPING_PARTIAL_MIN = 60.0
WIDENED_UNCLASSIFIED_STABLE_MAX = 2


__all__ = [
    "DEFAULT_AUTHORITY_SLICE_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_LIVE_RUN_OUT_DIR",
    "DEFAULT_PROFILE_STABILITY_OUT_DIR",
    "DEFAULT_V060_SUBSTRATE_PATH",
    "DEFAULT_V061_CLOSEOUT_PATH",
    "DEFAULT_V061_PROFILE_ADJUDICATION_PATH",
    "DEFAULT_V061_PROFILE_CLASSIFICATION_PATH",
    "LEGACY_BUCKETS",
    "LEGACY_BUCKET_MAPPING_PARTIAL_MIN",
    "LEGACY_BUCKET_MAPPING_READY_MIN",
    "SCHEMA_PREFIX",
    "WIDENED_UNCLASSIFIED_STABLE_MAX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
