from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_5_7_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_6_0"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REPRESENTATIVE_SUBSTRATE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_0_representative_substrate_current"
)
DEFAULT_DISPATCH_CLEANLINESS_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_0_dispatch_cleanliness_current"
)
DEFAULT_LEGACY_BUCKET_CLASSIFICATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_0_legacy_bucket_classification_current"
)
DEFAULT_AUTHORITY_ADMISSION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_0_authority_admission_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_6_0_closeout_current"
)

DEFAULT_V057_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_5_7_closeout_current" / "summary.json"
)
DEFAULT_V050_CANDIDATE_PACK_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_5_0_candidate_pack_current" / "summary.json"
)
DEFAULT_V0317_DISTRIBUTION_ANALYSIS_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_distribution_analysis_current" / "summary.json"
)

# v0.5.1 legacy bucket taxonomy — the canonical five buckets
LEGACY_BUCKETS = [
    "covered_success",
    "covered_but_fragile",
    "dispatch_or_policy_limited",
    "bounded_uncovered_subtype_candidate",
    "topology_or_open_world_spillover",
]

# Admission thresholds defined in PLAN_V0_6_0
DISPATCH_CLEANLINESS_PROMOTED_THRESHOLD = 20   # <= 20 → promoted
DISPATCH_CLEANLINESS_DEGRADED_THRESHOLD = 30   # <= 30 → degraded_but_executable, > 30 → failed
LEGACY_BUCKET_MAPPING_RATE_MIN = 60            # >= 60 → eligible for ready/partial


__all__ = [
    "DEFAULT_AUTHORITY_ADMISSION_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DISPATCH_CLEANLINESS_OUT_DIR",
    "DEFAULT_LEGACY_BUCKET_CLASSIFICATION_OUT_DIR",
    "DEFAULT_REPRESENTATIVE_SUBSTRATE_OUT_DIR",
    "DEFAULT_V050_CANDIDATE_PACK_PATH",
    "DEFAULT_V0317_DISTRIBUTION_ANALYSIS_PATH",
    "DEFAULT_V057_CLOSEOUT_PATH",
    "DISPATCH_CLEANLINESS_DEGRADED_THRESHOLD",
    "DISPATCH_CLEANLINESS_PROMOTED_THRESHOLD",
    "LEGACY_BUCKET_MAPPING_RATE_MIN",
    "LEGACY_BUCKETS",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
