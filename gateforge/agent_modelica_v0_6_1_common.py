from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_6_0_common import LEGACY_BUCKETS, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_6_1"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_1_handoff_integrity_current"
)
DEFAULT_LIVE_RUN_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_1_live_run_current"
)
DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_1_profile_classification_current"
)
DEFAULT_PROFILE_ADJUDICATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_1_profile_adjudication_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_1_closeout_current"
)

DEFAULT_V060_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_0_closeout_current" / "summary.json"
)
DEFAULT_V060_SUBSTRATE_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_0_representative_substrate_current" / "summary.json"
)
DEFAULT_V060_DISPATCH_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_0_dispatch_cleanliness_current" / "summary.json"
)
DEFAULT_V060_CLASSIFICATION_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_0_legacy_bucket_classification_current" / "summary.json"
)

LIVE_RUN_CASE_COUNT_REQUIRED = 24
LEGACY_BUCKET_MAPPING_READY_MIN = 80.0
LEGACY_BUCKET_MAPPING_PARTIAL_MIN = 60.0


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_LIVE_RUN_OUT_DIR",
    "DEFAULT_PROFILE_ADJUDICATION_OUT_DIR",
    "DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR",
    "DEFAULT_V060_CLASSIFICATION_PATH",
    "DEFAULT_V060_CLOSEOUT_PATH",
    "DEFAULT_V060_DISPATCH_PATH",
    "DEFAULT_V060_SUBSTRATE_PATH",
    "LEGACY_BUCKETS",
    "LEGACY_BUCKET_MAPPING_PARTIAL_MIN",
    "LEGACY_BUCKET_MAPPING_READY_MIN",
    "LIVE_RUN_CASE_COUNT_REQUIRED",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
