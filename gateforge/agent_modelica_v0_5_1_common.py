from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_5_0_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_5_1"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_1_frozen_slice_integrity_current"
DEFAULT_TAXONOMY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_1_boundary_taxonomy_current"
DEFAULT_CLASSIFICATION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_1_case_classification_current"
DEFAULT_READINESS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_1_boundary_readiness_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_1_closeout_current"

DEFAULT_V050_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_0_closeout_current" / "summary.json"

BOUNDARY_BUCKET_ORDER = [
    "covered_success",
    "covered_but_fragile",
    "dispatch_or_policy_limited",
    "bounded_uncovered_subtype_candidate",
    "topology_or_open_world_spillover",
    "boundary_ambiguous",
]


__all__ = [
    "BOUNDARY_BUCKET_ORDER",
    "DEFAULT_CLASSIFICATION_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_INTEGRITY_OUT_DIR",
    "DEFAULT_READINESS_OUT_DIR",
    "DEFAULT_TAXONOMY_OUT_DIR",
    "DEFAULT_V050_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
