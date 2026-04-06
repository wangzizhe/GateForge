from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_6_6_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_7_0"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_0_handoff_integrity_current"
)
DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_0_open_world_adjacent_substrate_current"
)
DEFAULT_LEGACY_BUCKET_AUDIT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_0_legacy_bucket_audit_current"
)
DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_0_substrate_admission_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_0_closeout_current"
)

DEFAULT_V060_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_0_closeout_current" / "summary.json"
)
DEFAULT_V061_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_1_closeout_current" / "summary.json"
)
DEFAULT_V062_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_2_closeout_current" / "summary.json"
)
DEFAULT_V066_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_6_closeout_current" / "summary.json"
)

LEGACY_BUCKETS = [
    "covered_success",
    "covered_but_fragile",
    "dispatch_or_policy_limited",
    "bounded_uncovered_subtype_candidate",
    "topology_or_open_world_spillover",
]

TASK_COUNT_MIN = 20
LEGACY_BUCKET_MAPPING_RATE_MIN = 70.0
UNCLASSIFIED_PENDING_MAX = 3
SPILLOVER_READY_MAX = 20.0
SPILLOVER_PARTIAL_MAX = 35.0
DISPATCH_AMBIGUITY_PROMOTED_MAX = 20.0
DISPATCH_AMBIGUITY_PARTIAL_MAX = 30.0


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_LEGACY_BUCKET_AUDIT_OUT_DIR",
    "DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR",
    "DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR",
    "DEFAULT_V060_CLOSEOUT_PATH",
    "DEFAULT_V061_CLOSEOUT_PATH",
    "DEFAULT_V062_CLOSEOUT_PATH",
    "DEFAULT_V066_CLOSEOUT_PATH",
    "DISPATCH_AMBIGUITY_PARTIAL_MAX",
    "DISPATCH_AMBIGUITY_PROMOTED_MAX",
    "LEGACY_BUCKETS",
    "LEGACY_BUCKET_MAPPING_RATE_MIN",
    "SCHEMA_PREFIX",
    "SPILLOVER_PARTIAL_MAX",
    "SPILLOVER_READY_MAX",
    "TASK_COUNT_MIN",
    "UNCLASSIFIED_PENDING_MAX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
